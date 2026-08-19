from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_public_information_scope_is_canonical() -> None:
    context = read("CONTEXT.md")
    protocol = read("PROJECT_AGENT_PROTOCOL.md")
    system_prompt = read("agent/core/v1.2/SYSTEM_PROMPT.md")
    workflow = read("agent/core/v1.2/WORKFLOW.md")
    readme = read("README.md")

    for text in (context, protocol, system_prompt, workflow, readme):
        assert "免费、公开、无需登录" in text

    assert "从未使用目标法律AI产品、希望先建立基本认识的普通读者" in protocol
    assert "不预设其具备法律、技术、采购或投资专业背景" in protocol
    assert "不注册目标产品账号" in protocol
    assert "不对目标产品的准确率" in protocol
    assert "PASS 只表示本项目的公开信息研究" in protocol
    assert "项目不注册或登录目标产品" in workflow
    assert "不测试准确率、稳定性或实际效果" in workflow
    assert "不能通过取得同意转化为本项目步骤" in system_prompt


def test_domain_glossary_unifies_audience_purpose_scope_and_delivery() -> None:
    context = read("CONTEXT.md")
    protocol = read("PROJECT_AGENT_PROTOCOL.md")
    workflow = read("agent/core/v1.2/WORKFLOW.md")
    readme = read("README.md")

    for term in (
        "目标读者",
        "项目目的",
        "分析范围",
        "报告流程状态",
        "主交付物",
        "审计交付物",
        "渲染交付物",
        "对话交付",
    ):
        assert f"**{term}**" in context

    for text in (context, protocol, workflow):
        assert "不替代主交付物" in text

    assert "完整分析范围" not in workflow
    assert "知识库写入完成或待入库记录已生成" in protocol
    assert "不评价、测试或推荐目标产品" in readme


def test_agent_adapters_repeat_scope_boundary() -> None:
    for relative in ("AGENTS.md", "CLAUDE.md", "GEMINI.md"):
        text = read(relative)
        assert "free, public, no-login information" in text
        assert "Never register or log in to the target product" in text
        assert "A PASS validates this project's research and document pipeline" in text


def test_public_information_release_metadata_and_guide() -> None:
    manifest = read("VERSION_MANIFEST.yaml")
    assert 'project_phase: "P3.9"' in manifest
    assert 'canonical_domain_glossary: "CONTEXT.md"' in manifest
    assert 'release_channel: "public-information"' in manifest
    assert "target_product_function_testing_allowed: false" in manifest
    assert "target_product_accuracy_claims_allowed: false" in manifest

    assert (ROOT / "docs/PUBLIC_INFORMATION_GUIDE.md").is_file()
    assert not (ROOT / "docs/USER_TRIAL_GUIDE.md").exists()

    profile = read("evaluations/p3_tongyifarui_acceptance.json")
    assert "公开信息报告回归" in profile
    assert "真实试用回归" not in profile


def test_restricted_product_actions_are_not_waiting_authorization_steps() -> None:
    system_prompt = read("agent/core/v1.2/SYSTEM_PROMPT.md")
    workflow = read("agent/core/v1.2/WORKFLOW.md")
    assert "受限部分必须保持“等待授权”" not in system_prompt
    assert "使用用户账号、登录态、验证码" not in workflow
    assert "不属于本项目" in workflow