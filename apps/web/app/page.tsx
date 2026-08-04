"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

type Candidate = {
  id: string;
  product_name: string;
  operator_name: string;
  product_type: string;
  is_legal_ai: boolean;
};

type TaskEvent = {
  event_type: string;
  from_status: string | null;
  to_status: string;
  reason: string;
  occurred_at: string;
};

type Task = {
  task_id: string;
  submitted_product_name: string;
  canonical_product_name: string | null;
  operator_name: string | null;
  product_type: string | null;
  task_status: string;
  identity_gate: string;
  clarification_question: string | null;
  candidates: Candidate[];
  related_product_hints: string[];
  status_message: string;
  next_action: string | null;
  phase_limit_reached: boolean;
  created_at: string;
  events: TaskEvent[];
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const detail = typeof payload.detail === "string" ? payload.detail : "请求失败，请检查本地API是否已启动";
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

function statusClass(status: string) {
  if (status === "研究中") return "badge badge-ready";
  if (status === "已终止") return "badge badge-stopped";
  return "badge badge-waiting";
}

export default function Home() {
  const [productName, setProductName] = useState("");
  const [confirmedName, setConfirmedName] = useState("");
  const [currentTask, setCurrentTask] = useState<Task | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const taskCount = useMemo(() => tasks.length, [tasks]);

  async function refreshTasks() {
    try {
      const data = await request<Task[]>("/api/tasks");
      setTasks(data);
    } catch {
      // The page remains usable before the local API is started.
    }
  }

  useEffect(() => {
    void refreshTasks();
  }, []);

  async function submitProduct(event: FormEvent) {
    event.preventDefault();
    if (!productName.trim()) {
      setError("请先输入产品名称");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const task = await request<Task>("/api/tasks", {
        method: "POST",
        body: JSON.stringify({ product_name: productName }),
      });
      setCurrentTask(task);
      setConfirmedName("");
      await refreshTasks();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "提交失败");
    } finally {
      setLoading(false);
    }
  }

  async function clarify(payload: { candidate_id?: string; confirmed_product_name?: string }) {
    if (!currentTask) return;
    setLoading(true);
    setError("");
    try {
      const task = await request<Task>(`/api/tasks/${currentTask.task_id}/clarifications`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setCurrentTask(task);
      setConfirmedName("");
      await refreshTasks();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "确认失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <section className="hero">
        <div className="eyebrow">LEGAL AI PRODUCT INTELLIGENCE</div>
        <h1>先确认产品，<br />再开始分析。</h1>
        <p className="hero-copy">单用户本地最小闭环 · Agent核心 V1.1</p>
        <div className="phase-strip" aria-label="当前实现进度">
          <span className="phase active">01 产品输入</span>
          <span className="phase active">02 身份闸门</span>
          <span className="phase active">03 澄清确认</span>
          <span className="phase muted">04 公开研究</span>
          <span className="phase muted">05 Word报告</span>
        </div>
      </section>

      <div className="workspace-grid">
        <section className="panel input-panel">
          <div className="panel-heading">
            <span className="step-number">01</span>
            <div>
              <h2>提交分析对象</h2>
              <p>唯一必填项是法律AI产品名称。</p>
            </div>
          </div>
          <form onSubmit={submitProduct}>
            <label htmlFor="product">产品名称</label>
            <div className="input-row">
              <input
                id="product"
                value={productName}
                onChange={(event) => setProductName(event.target.value)}
                placeholder="例如：输入完整产品名称"
                maxLength={120}
                autoComplete="off"
              />
              <button type="submit" disabled={loading}>{loading ? "处理中…" : "开始识别"}</button>
            </div>
          </form>
          <div className="test-note">
            <strong>本地测试名称</strong>
            <span>衡法智研（明确）</span>
            <span>星云助手（需澄清）</span>
            <span>晴空天气（越界）</span>
          </div>
          {error && <p className="error" role="alert">{error}</p>}
        </section>

        <aside className="panel scope-panel">
          <span className="label">P2.1 范围</span>
          <h2>边界被写进流程</h2>
          <ul>
            <li>名称不清楚，就停下询问</li>
            <li>确认前不扩展产品生态</li>
            <li>非法律AI产品直接终止</li>
            <li>不建库、不训练、不调用真实模型</li>
          </ul>
          <div className="local-pill"><span /> 本地内存模式 · 重启即清空</div>
        </aside>
      </div>

      {currentTask && (
        <section className="panel result-panel" aria-live="polite">
          <div className="result-topline">
            <div>
              <span className="label">当前任务</span>
              <h2>{currentTask.canonical_product_name ?? currentTask.submitted_product_name}</h2>
            </div>
            <span className={statusClass(currentTask.task_status)}>{currentTask.task_status}</span>
          </div>
          <p className="status-message">{currentTask.status_message}</p>

          {currentTask.task_status === "等待产品确认" && (
            <div className="clarification">
              <h3>{currentTask.clarification_question}</h3>
              {currentTask.candidates.length > 0 && (
                <div className="candidate-grid">
                  {currentTask.candidates.map((candidate) => (
                    <button
                      className="candidate"
                      key={candidate.id}
                      disabled={loading}
                      onClick={() => void clarify({ candidate_id: candidate.id })}
                    >
                      <strong>{candidate.product_name}</strong>
                      <span>{candidate.operator_name}</span>
                      <small>{candidate.product_type}</small>
                    </button>
                  ))}
                </div>
              )}
              <div className="confirm-row">
                <input
                  value={confirmedName}
                  onChange={(event) => setConfirmedName(event.target.value)}
                  placeholder="或填写你确认的确切产品全称"
                  maxLength={120}
                />
                <button
                  type="button"
                  className="secondary"
                  disabled={loading || !confirmedName.trim()}
                  onClick={() => void clarify({ confirmed_product_name: confirmedName })}
                >确认名称</button>
              </div>
              <p className="guard-note">这是输入澄清，不是权限申请。确认前系统不会继续后续步骤。</p>
            </div>
          )}

          {currentTask.canonical_product_name && (
            <dl className="facts">
              <div><dt>标准产品名</dt><dd>{currentTask.canonical_product_name}</dd></div>
              <div><dt>运营主体</dt><dd>{currentTask.operator_name ?? "待公开核验"}</dd></div>
              <div><dt>产品类型</dt><dd>{currentTask.product_type ?? "待公开核验"}</dd></div>
              <div><dt>身份闸门</dt><dd>{currentTask.identity_gate}</dd></div>
            </dl>
          )}

          {currentTask.related_product_hints.length > 0 && (
            <div className="related">
              <h3>后续需一并核验的关联线索</h3>
              {currentTask.related_product_hints.map((item) => <span key={item}>{item}</span>)}
            </div>
          )}

          {currentTask.phase_limit_reached && (
            <div className="phase-limit"><strong>P2.1 已到达阶段终点</strong><span>{currentTask.next_action}</span></div>
          )}
          <p className="task-id">任务 ID · {currentTask.task_id}</p>
        </section>
      )}

      <section className="history">
        <div className="history-heading">
          <div><span className="label">本次运行</span><h2>任务记录</h2></div>
          <span>{taskCount} 条</span>
        </div>
        {tasks.length === 0 ? (
          <p className="empty">尚未提交产品。启动本地API后，任务会显示在这里。</p>
        ) : (
          <div className="task-list">
            {tasks.map((task) => (
              <button key={task.task_id} className="task-row" onClick={() => setCurrentTask(task)}>
                <span><strong>{task.canonical_product_name ?? task.submitted_product_name}</strong><small>{new Date(task.created_at).toLocaleString("zh-CN")}</small></span>
                <span className={statusClass(task.task_status)}>{task.task_status}</span>
              </button>
            ))}
          </div>
        )}
      </section>

      <footer>法律AI分析Agent · 本页面仅验证身份闸门与状态流转，不提供法律意见。</footer>
    </main>
  );
}
