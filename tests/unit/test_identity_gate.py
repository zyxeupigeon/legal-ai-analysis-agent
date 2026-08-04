from services.api.app.identity_gate import evaluate_product_name


def test_clear_legal_ai_fixture() -> None:
    decision = evaluate_product_name("衡法智研")
    assert decision.outcome == "clear"
    assert decision.product is not None
    assert decision.product.is_legal_ai is True
    assert len(decision.product.related_product_hints) == 2


def test_ambiguous_fixture_returns_candidates_without_guessing() -> None:
    decision = evaluate_product_name("星云助手")
    assert decision.outcome == "ambiguous"
    assert len(decision.candidates) == 2
    assert {item.product_name for item in decision.candidates} == {"星云法律助手", "星云通用AI助手"}


def test_generic_term_stops_for_clarification() -> None:
    decision = evaluate_product_name("法律AI")
    assert decision.outcome == "ambiguous"
    assert decision.question
    assert decision.candidates == []


def test_multiple_names_stop_for_clarification() -> None:
    decision = evaluate_product_name("产品甲或产品乙")
    assert decision.outcome == "ambiguous"


def test_unknown_name_is_not_auto_confirmed() -> None:
    decision = evaluate_product_name("现实中可能存在的产品")
    assert decision.outcome == "ambiguous"
    assert "不能用模型常识" in decision.message


def test_non_legal_fixture_is_rejected() -> None:
    decision = evaluate_product_name("晴空天气")
    assert decision.outcome == "rejected"
    assert decision.product is not None
    assert decision.product.is_legal_ai is False
