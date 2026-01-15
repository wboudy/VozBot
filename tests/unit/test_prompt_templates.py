"""Tests for bilingual prompt templates."""

from __future__ import annotations

import pytest

from vozbot.agent.prompts.templates import (
    CONFIRMATION_TEMPLATE,
    ERROR_RETRY_TEMPLATE,
    ERROR_TEMPLATE,
    ESCALATION_IMMEDIATE_TEMPLATE,
    ESCALATION_UNAVAILABLE_TEMPLATE,
    FAREWELL_TEMPLATE,
    FAREWELL_TRANSFER_TEMPLATE,
    GREETING_TEMPLATE,
    INFO_COLLECTION_CALLBACK_TEMPLATE,
    INFO_COLLECTION_NAME_TEMPLATE,
    INFO_COLLECTION_TIME_TEMPLATE,
    INTENT_CLARIFICATION_TEMPLATE,
    INTENT_DISCOVERY_TEMPLATE,
    STATE_TEMPLATES,
    SYSTEM_PROMPT,
    PromptTemplate,
    TemplateType,
    get_all_templates,
    get_system_prompt,
    get_template_for_state,
)
from vozbot.agent.state_machine.states import CallState


class TestPromptTemplate:
    """Tests for PromptTemplate dataclass."""

    def test_render_english_default(self) -> None:
        """Test that English is the default language."""
        template = PromptTemplate(
            template_type=TemplateType.GREETING,
            en="Hello!",
            es="Hola!",
        )

        result = template.render()
        assert result == "Hello!"

    def test_render_spanish(self) -> None:
        """Test Spanish rendering."""
        template = PromptTemplate(
            template_type=TemplateType.GREETING,
            en="Hello!",
            es="Hola!",
        )

        result = template.render(language="es")
        assert result == "Hola!"

    def test_render_with_variables(self) -> None:
        """Test variable substitution."""
        template = PromptTemplate(
            template_type=TemplateType.GREETING,
            en="Hello, {name}!",
            es="Hola, {name}!",
        )

        result = template.render(name="John")
        assert result == "Hello, John!"

    def test_render_spanish_with_variables(self) -> None:
        """Test Spanish rendering with variables."""
        template = PromptTemplate(
            template_type=TemplateType.GREETING,
            en="Hello, {name}!",
            es="Hola, {name}!",
        )

        result = template.render(language="es", name="Juan")
        assert result == "Hola, Juan!"

    def test_render_missing_variable_returns_template(self) -> None:
        """Test that missing variables don't crash."""
        template = PromptTemplate(
            template_type=TemplateType.GREETING,
            en="Hello, {name}!",
            es="Hola, {name}!",
        )

        # Should not raise, returns template as-is
        result = template.render()
        assert result == "Hello, {name}!"

    def test_render_partial_variables(self) -> None:
        """Test rendering with some variables missing."""
        template = PromptTemplate(
            template_type=TemplateType.CONFIRMATION,
            en="Name: {name}, Phone: {phone}",
            es="Nombre: {name}, Telefono: {phone}",
        )

        # Only provide one variable
        result = template.render(name="John")
        # Should return template as-is since phone is missing
        assert result == "Name: {name}, Phone: {phone}"


class TestAllTemplatesHaveBothLanguages:
    """Tests to verify all templates have both English and Spanish."""

    def test_system_prompt_has_both_languages(self) -> None:
        """Test system prompt has en and es."""
        assert SYSTEM_PROMPT.en
        assert SYSTEM_PROMPT.es
        assert len(SYSTEM_PROMPT.en) > 100
        assert len(SYSTEM_PROMPT.es) > 100

    def test_greeting_template_has_both_languages(self) -> None:
        """Test greeting template has en and es."""
        assert GREETING_TEMPLATE.en
        assert GREETING_TEMPLATE.es

    def test_intent_discovery_template_has_both_languages(self) -> None:
        """Test intent discovery template has en and es."""
        assert INTENT_DISCOVERY_TEMPLATE.en
        assert INTENT_DISCOVERY_TEMPLATE.es

    def test_intent_clarification_template_has_both_languages(self) -> None:
        """Test intent clarification template has en and es."""
        assert INTENT_CLARIFICATION_TEMPLATE.en
        assert INTENT_CLARIFICATION_TEMPLATE.es

    def test_info_collection_templates_have_both_languages(self) -> None:
        """Test info collection templates have en and es."""
        assert INFO_COLLECTION_NAME_TEMPLATE.en
        assert INFO_COLLECTION_NAME_TEMPLATE.es
        assert INFO_COLLECTION_CALLBACK_TEMPLATE.en
        assert INFO_COLLECTION_CALLBACK_TEMPLATE.es
        assert INFO_COLLECTION_TIME_TEMPLATE.en
        assert INFO_COLLECTION_TIME_TEMPLATE.es

    def test_confirmation_template_has_both_languages(self) -> None:
        """Test confirmation template has en and es."""
        assert CONFIRMATION_TEMPLATE.en
        assert CONFIRMATION_TEMPLATE.es

    def test_escalation_templates_have_both_languages(self) -> None:
        """Test escalation templates have en and es."""
        assert ESCALATION_IMMEDIATE_TEMPLATE.en
        assert ESCALATION_IMMEDIATE_TEMPLATE.es
        assert ESCALATION_UNAVAILABLE_TEMPLATE.en
        assert ESCALATION_UNAVAILABLE_TEMPLATE.es

    def test_error_templates_have_both_languages(self) -> None:
        """Test error templates have en and es."""
        assert ERROR_TEMPLATE.en
        assert ERROR_TEMPLATE.es
        assert ERROR_RETRY_TEMPLATE.en
        assert ERROR_RETRY_TEMPLATE.es

    def test_farewell_templates_have_both_languages(self) -> None:
        """Test farewell templates have en and es."""
        assert FAREWELL_TEMPLATE.en
        assert FAREWELL_TEMPLATE.es
        assert FAREWELL_TRANSFER_TEMPLATE.en
        assert FAREWELL_TRANSFER_TEMPLATE.es

    def test_all_templates_function_returns_all(self) -> None:
        """Test get_all_templates returns all templates."""
        templates = get_all_templates()
        assert len(templates) >= 14  # At least 14 templates defined

        # All should have both languages
        for template in templates:
            assert template.en, f"Template {template.template_type} missing English"
            assert template.es, f"Template {template.template_type} missing Spanish"


class TestSystemPromptContent:
    """Tests for system prompt content and security."""

    def test_system_prompt_includes_role(self) -> None:
        """Test system prompt includes role definition."""
        assert "role" in SYSTEM_PROMPT.en.lower()
        assert "VozBot" in SYSTEM_PROMPT.en

    def test_system_prompt_includes_guardrails(self) -> None:
        """Test system prompt includes security guardrails."""
        en = SYSTEM_PROMPT.en.lower()
        assert "guardrail" in en or "rule" in en
        assert "never" in en
        assert "ssn" in en
        assert "date of birth" in en or "dob" in en
        assert "credit card" in en

    def test_system_prompt_includes_tool_usage(self) -> None:
        """Test system prompt includes tool usage instructions."""
        en = SYSTEM_PROMPT.en.lower()
        assert "tool" in en
        assert "create_call_record" in en
        assert "create_callback_task" in en

    def test_system_prompt_injection_defense(self) -> None:
        """Test system prompt has prompt injection defenses."""
        en = SYSTEM_PROMPT.en.lower()
        # Should mention not following contradicting instructions
        assert "contradict" in en or "ignore" in en
        # Should mention not revealing system prompts
        assert "reveal" in en or "internal" in en

    def test_system_prompt_spanish_version_complete(self) -> None:
        """Test Spanish system prompt has equivalent content."""
        es = SYSTEM_PROMPT.es.lower()
        assert "vozbot" in es
        assert "nunca" in es  # NEVER in Spanish
        assert "ssn" in es
        assert "herramienta" in es  # Tool in Spanish


class TestGetSystemPrompt:
    """Tests for get_system_prompt function."""

    def test_get_system_prompt_english(self) -> None:
        """Test getting English system prompt."""
        prompt = get_system_prompt(
            language="en",
            call_id="call-123",
            current_state="GREET",
            additional_context="Customer is new",
        )

        assert "call-123" in prompt
        assert "GREET" in prompt
        assert "Customer is new" in prompt

    def test_get_system_prompt_spanish(self) -> None:
        """Test getting Spanish system prompt."""
        prompt = get_system_prompt(
            language="es",
            call_id="call-456",
            current_state="INTENT_DISCOVERY",
        )

        assert "call-456" in prompt
        # Should be Spanish text
        assert "Restricciones" in prompt or "reglas" in prompt.lower()


class TestGetTemplateForState:
    """Tests for get_template_for_state function."""

    def test_get_greet_template(self) -> None:
        """Test getting template for GREET state."""
        template = get_template_for_state(CallState.GREET)
        assert template is not None
        assert template.template_type == TemplateType.GREETING

    def test_get_intent_discovery_template(self) -> None:
        """Test getting template for INTENT_DISCOVERY state."""
        template = get_template_for_state(CallState.INTENT_DISCOVERY)
        assert template is not None

    def test_get_info_collection_templates(self) -> None:
        """Test getting multiple templates for INFO_COLLECTION state."""
        template0 = get_template_for_state(CallState.INFO_COLLECTION, 0)
        template1 = get_template_for_state(CallState.INFO_COLLECTION, 1)
        template2 = get_template_for_state(CallState.INFO_COLLECTION, 2)

        assert template0 is not None
        assert template1 is not None
        assert template2 is not None
        # They should be different templates
        assert template0.en != template1.en

    def test_get_template_invalid_index(self) -> None:
        """Test getting template with invalid index returns None."""
        template = get_template_for_state(CallState.GREET, 999)
        assert template is None

    def test_get_template_no_template_state(self) -> None:
        """Test getting template for state without templates."""
        # INIT state likely has no template
        template = get_template_for_state(CallState.INIT)
        assert template is None


class TestStateTemplatesMapping:
    """Tests for STATE_TEMPLATES mapping."""

    def test_greet_state_has_templates(self) -> None:
        """Test GREET state has templates."""
        assert CallState.GREET in STATE_TEMPLATES
        assert len(STATE_TEMPLATES[CallState.GREET]) >= 1

    def test_intent_discovery_has_templates(self) -> None:
        """Test INTENT_DISCOVERY has templates."""
        assert CallState.INTENT_DISCOVERY in STATE_TEMPLATES
        assert len(STATE_TEMPLATES[CallState.INTENT_DISCOVERY]) >= 2

    def test_info_collection_has_templates(self) -> None:
        """Test INFO_COLLECTION has templates."""
        assert CallState.INFO_COLLECTION in STATE_TEMPLATES
        assert len(STATE_TEMPLATES[CallState.INFO_COLLECTION]) >= 3

    def test_confirmation_has_templates(self) -> None:
        """Test CONFIRMATION has templates."""
        assert CallState.CONFIRMATION in STATE_TEMPLATES

    def test_error_has_templates(self) -> None:
        """Test ERROR state has templates."""
        assert CallState.ERROR in STATE_TEMPLATES
        assert len(STATE_TEMPLATES[CallState.ERROR]) >= 2

    def test_end_has_templates(self) -> None:
        """Test END state has templates."""
        assert CallState.END in STATE_TEMPLATES


class TestTemplateRendering:
    """Tests for rendering templates with actual values."""

    def test_greeting_template_renders(self) -> None:
        """Test greeting template renders with business name."""
        result = GREETING_TEMPLATE.render(business_name="Acme Dental")
        assert "Acme Dental" in result
        assert "AI assistant" in result

    def test_confirmation_template_renders(self) -> None:
        """Test confirmation template renders all fields."""
        result = CONFIRMATION_TEMPLATE.render(
            name="John Doe",
            callback_number="+15551234567",
            best_time="morning",
            intent="Schedule dental appointment",
        )

        assert "John Doe" in result
        assert "+15551234567" in result
        assert "morning" in result
        assert "dental appointment" in result

    def test_farewell_template_renders(self) -> None:
        """Test farewell template renders."""
        result = FAREWELL_TEMPLATE.render(
            business_name="Acme Dental",
            callback_timeframe="within the next hour",
        )

        assert "Acme Dental" in result
        assert "within the next hour" in result

    def test_intent_clarification_renders(self) -> None:
        """Test intent clarification template renders."""
        result = INTENT_CLARIFICATION_TEMPLATE.render(
            partial_intent="scheduling a dental appointment",
        )

        assert "scheduling a dental appointment" in result

    def test_spanish_rendering_with_variables(self) -> None:
        """Test Spanish rendering with variable substitution."""
        result = GREETING_TEMPLATE.render(
            language="es",
            business_name="Clinica Dental",
        )

        assert "Clinica Dental" in result
        assert "inteligencia artificial" in result


class TestTemplatesLoadWithoutError:
    """Tests to verify all templates can be imported and accessed."""

    def test_import_all_templates(self) -> None:
        """Test that all templates can be imported."""
        from vozbot.agent.prompts import (
            CONFIRMATION_TEMPLATE,
            ERROR_RETRY_TEMPLATE,
            ERROR_TEMPLATE,
            ESCALATION_IMMEDIATE_TEMPLATE,
            ESCALATION_UNAVAILABLE_TEMPLATE,
            FAREWELL_TEMPLATE,
            FAREWELL_TRANSFER_TEMPLATE,
            GREETING_TEMPLATE,
            INFO_COLLECTION_CALLBACK_TEMPLATE,
            INFO_COLLECTION_NAME_TEMPLATE,
            INFO_COLLECTION_TIME_TEMPLATE,
            INTENT_CLARIFICATION_TEMPLATE,
            INTENT_DISCOVERY_TEMPLATE,
            SYSTEM_PROMPT,
        )

        # Just verify they're all PromptTemplate instances
        assert isinstance(SYSTEM_PROMPT, PromptTemplate)
        assert isinstance(GREETING_TEMPLATE, PromptTemplate)
        assert isinstance(INTENT_DISCOVERY_TEMPLATE, PromptTemplate)
        assert isinstance(INTENT_CLARIFICATION_TEMPLATE, PromptTemplate)
        assert isinstance(INFO_COLLECTION_NAME_TEMPLATE, PromptTemplate)
        assert isinstance(INFO_COLLECTION_CALLBACK_TEMPLATE, PromptTemplate)
        assert isinstance(INFO_COLLECTION_TIME_TEMPLATE, PromptTemplate)
        assert isinstance(CONFIRMATION_TEMPLATE, PromptTemplate)
        assert isinstance(ESCALATION_IMMEDIATE_TEMPLATE, PromptTemplate)
        assert isinstance(ESCALATION_UNAVAILABLE_TEMPLATE, PromptTemplate)
        assert isinstance(ERROR_TEMPLATE, PromptTemplate)
        assert isinstance(ERROR_RETRY_TEMPLATE, PromptTemplate)
        assert isinstance(FAREWELL_TEMPLATE, PromptTemplate)
        assert isinstance(FAREWELL_TRANSFER_TEMPLATE, PromptTemplate)

    def test_module_init_exports(self) -> None:
        """Test that __init__.py exports all templates."""
        from vozbot.agent.prompts import (
            STATE_TEMPLATES,
            get_all_templates,
            get_system_prompt,
            get_template_for_state,
        )

        assert callable(get_system_prompt)
        assert callable(get_template_for_state)
        assert callable(get_all_templates)
        assert isinstance(STATE_TEMPLATES, dict)
