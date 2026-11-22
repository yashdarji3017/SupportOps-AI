import asyncio

from backend.app.core.concurrency import concurrency_limiter
from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.schemas.classification import QueryClassification
from backend.app.schemas.response import (
    BatchAnalysisResponse,
    BatchItemFailure,
    TicketAnalysisResponse,
)
from backend.app.schemas.ticket import BatchTicketRequest, TicketPriority, TicketRequest
from backend.app.services.classification import classification_service
from backend.app.services.classifier_agent import (
    ClassifierAgentProtocol,
    LLMInvalidResponseError,
    LLMProviderError,
    LLMTimeoutError,
    get_classifier_agent,
    set_classifier_agent,
)
from backend.app.services.escalation import escalation_engine
from backend.app.services.metrics import metrics_service
from backend.app.services.reply_generator import reply_safety_service
from backend.app.services.session_manager import session_manager


class TicketAnalyzerService:
    """Service that coordinates ticket analysis, concurrency control, and escalation."""

    def __init__(self, agent: ClassifierAgentProtocol | None = None) -> None:
        """Initialize TicketAnalyzerService with a classifier agent instance.

        Args:
            agent: Optional preconfigured agent conforming to ClassifierAgentProtocol.
        """
        self._agent: ClassifierAgentProtocol = agent or get_classifier_agent()

    @property
    def agent(self) -> ClassifierAgentProtocol:
        """Retrieve active ClassifierAgentProtocol instance."""
        return self._agent

    @agent.setter
    def agent(self, new_agent: ClassifierAgentProtocol) -> None:
        """Set and register a new active ClassifierAgentProtocol instance.

        Args:
            new_agent: The ClassifierAgentProtocol instance to activate.
        """
        self._agent = new_agent
        set_classifier_agent(new_agent)

    @property
    def provider(self) -> ClassifierAgentProtocol:
        """Backward compatibility alias for tests accessing .provider."""
        return self._agent

    @provider.setter
    def provider(self, new_agent: ClassifierAgentProtocol) -> None:
        """Backward compatibility setter for tests setting .provider.

        Args:
            new_agent: The ClassifierAgentProtocol instance to activate.
        """
        self.agent = new_agent

    async def analyze_ticket(self, request: TicketRequest) -> TicketAnalysisResponse:
        """Process a single support ticket through the complete triage pipeline.

        Executes session creation, semaphore acquisition, model classification,
        independent escalation policy enforcement, suggested reply sanitization,
        and metrics collection.

        Args:
            request: The incoming TicketRequest to process.

        Returns:
            A validated TicketAnalysisResponse with full triage results.

        Raises:
            TimeoutError: If concurrency permit wait times out.
            Exception: If an unhandled execution exception occurs.
        """
        async with session_manager.create_session(ticket_id=request.ticket_id) as session_ctx:
            request_id = session_ctx.request_id
            ticket_id = session_ctx.ticket_id

            logger.info("Processing ticket %s (subject: '%s...')", ticket_id, request.subject[:50])

            async with concurrency_limiter.acquire(timeout=settings.REQUEST_TIMEOUT_SECONDS):
                try:
                    llm_result: QueryClassification | None = None
                    provider_failed = False
                    provider_error_msg = ""

                    try:
                        analyze_method = getattr(self._agent, "analyze_ticket", None)
                        if callable(analyze_method):
                            llm_result = await analyze_method(
                                subject=request.subject,
                                description=request.description,
                                customer_name=request.customer_name,
                            )
                        else:
                            name_prefix = (
                                f"Customer Name: {request.customer_name.strip()}\n"
                                if request.customer_name and request.customer_name.strip()
                                else ""
                            )
                            query = f"{name_prefix}Subject: {request.subject}\nDescription: {request.description}"
                            llm_result = await self._agent.classify(query)

                    except (
                        LLMTimeoutError,
                        LLMInvalidResponseError,
                        LLMProviderError,
                        Exception,
                    ) as exc:
                        provider_failed = True
                        provider_error_msg = str(exc)
                        logger.error("Classifier agent failed for ticket %s: %s", ticket_id, exc)

                    if provider_failed or llm_result is None:
                        fallback_category = classification_service.classify_heuristics(
                            f"{request.subject} {request.description}"
                        )
                        response = TicketAnalysisResponse(
                            ticket_id=ticket_id,
                            request_id=request_id,
                            category=fallback_category,
                            priority=TicketPriority.HIGH,
                            confidence_score=0.0,
                            suggested_reply=None,
                            requires_human=True,
                            escalation_reason=(
                                f"Mandatory escalation: AI provider failure ({provider_error_msg}). "
                                "Forwarded to human support."
                            ),
                        )
                        await metrics_service.record_processed(is_escalated=True)
                        return response

                    is_escalated, escalation_reason = escalation_engine.enforce_policy(
                        subject=request.subject,
                        description=request.description,
                        llm_result=llm_result,
                        threshold=settings.CONFIDENCE_THRESHOLD,
                    )

                    final_reply = reply_safety_service.sanitize_reply(
                        reply=llm_result.suggested_reply,
                        requires_human=is_escalated,
                        category=llm_result.category,
                    )

                    response = TicketAnalysisResponse(
                        ticket_id=ticket_id,
                        request_id=request_id,
                        category=llm_result.category,
                        priority=llm_result.priority,
                        confidence_score=llm_result.confidence_score,
                        suggested_reply=final_reply,
                        requires_human=is_escalated,
                        escalation_reason=escalation_reason if is_escalated else None,
                    )

                    await metrics_service.record_processed(is_escalated=is_escalated)
                    return response

                except Exception as exc:
                    await metrics_service.record_failure()
                    logger.error("Unexpected error processing ticket %s: %s", ticket_id, exc)
                    raise

    async def analyze_batch(self, batch_request: BatchTicketRequest) -> BatchAnalysisResponse:
        """Process a collection of tickets concurrently with isolated error handling.

        Args:
            batch_request: BatchTicketRequest container holding ticket items.

        Returns:
            BatchAnalysisResponse aggregating successful results and failures.
        """
        total = len(batch_request.tickets)
        logger.info("Initiating batch processing for %d tickets", total)

        async def _safe_process(t: TicketRequest) -> TicketAnalysisResponse | Exception:
            """Process an individual ticket safely, capturing any exception.

            Args:
                t: The TicketRequest to analyze.

            Returns:
                TicketAnalysisResponse on success, or the Exception raised on failure.
            """
            try:
                return await self.analyze_ticket(t)
            except Exception as e:
                return e

        tasks = [_safe_process(t) for t in batch_request.tickets]
        raw_results = await asyncio.gather(*tasks)

        successful: list[TicketAnalysisResponse] = []
        failures: list[BatchItemFailure] = []

        for idx, res in enumerate(raw_results):
            original_ticket = batch_request.tickets[idx]
            if isinstance(res, TicketAnalysisResponse):
                successful.append(res)
            elif isinstance(res, Exception):
                failures.append(
                    BatchItemFailure(
                        ticket_id=original_ticket.ticket_id,
                        request_id="batch-failed",
                        error=str(res),
                    )
                )
            else:
                failures.append(
                    BatchItemFailure(
                        ticket_id=original_ticket.ticket_id,
                        request_id="batch-unknown",
                        error="Unknown error during processing",
                    )
                )

        return BatchAnalysisResponse(
            total_tickets=total,
            successful_count=len(successful),
            failed_count=len(failures),
            results=successful,
            errors=failures,
        )


ticket_analyzer_service: TicketAnalyzerService = TicketAnalyzerService()
