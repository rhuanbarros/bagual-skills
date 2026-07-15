#!/usr/bin/env python3
"""test_gerente_quota.py — provas reais (subprocessos, não mocks) dos invariantes de E8.3.

Story E8.3 — roda `gerente_quota.py` como subprocessos de verdade contra fixtures reais
de `~/.claude/rate-limits-state.json` (schema observado em produção) para provar:

  1. `read-limits` parseia o schema real (`five_hour.used_percentage`,
     `seven_day.used_percentage`, `updated_at` epoch) e nunca lança exceção para
     arquivo ausente/malformado/com schema inesperado (só `ok: false` + `error`).
  2. `record-usage` acumula tokens (com o multiplicador de segurança aplicado e
     arredondado para cima) e reseta automaticamente quando `--cycle-id` muda.
  3. `check` — CASO CENTRAL da story: snapshot CONGELADO reportando uso baixo +
     auto-rastreio alto → o sinal auto-rastreado (mais conservador) VENCE, veredito
     `stop`. E o inverso: rate-limit fresco alto vence quando o auto-rastreio está baixo.
  4. Comparação de limiar sem off-by-one (`>= threshold` para, `< threshold` segue) e
     sem mistura de unidades (tudo em % consistentemente).
  5. `check --stop-diario` grava `parei-por-cota` em diario.md/diario.jsonl via o mesmo
     mecanismo append-diario de E8.2 (reuso, não reimplementação).
  6. Precedência de config (CLI > env var > quota.config.json > default hardcoded).
  7. Primeiro ciclo de sempre (rate-limit ausente + self-tracked zerado) não causa
     falso-stop — verdict `start`, apenas `degraded: true` sinalizado.

Sem dependências externas (stdlib apenas).

Uso:
    python3 test_gerente_quota.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "gerente_quota.py"


def run(args: list[str], env: dict | None = None) -> subprocess.CompletedProcess:
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    # Isola de qualquer GERENTE_QUOTA_* herdado do ambiente do desenvolvedor/CI.
    for k in list(full_env):
        if k.startswith("GERENTE_QUOTA_") and (not env or k not in env):
            del full_env[k]
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, env=full_env,
    )


def run_json(args: list[str], env: dict | None = None) -> dict:
    p = run(args, env=env)
    out = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else "{}"
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        print("STDOUT:", p.stdout, file=sys.stderr)
        print("STDERR:", p.stderr, file=sys.stderr)
        raise


PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        PASS.append(name)
        print(f"  PASS  {name}")
    else:
        FAIL.append(name)
        print(f"  FAIL  {name}  {detail}")


def write_limits(path: Path, five_hour_pct: float, seven_day_pct: float, age_seconds: float = 0.0, model: str = "Opus 4.8 (1M context)") -> None:
    now = time.time()
    updated_at = int(now - age_seconds)
    path.write_text(json.dumps({
        "updated_at": updated_at,
        "model": model,
        "five_hour": {"used_percentage": five_hour_pct, "resets_at": updated_at + 18000},
        "seven_day": {"used_percentage": seven_day_pct, "resets_at": updated_at + 36000},
    }), encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="gerente-quota-test-") as tmp:
        tmp_path = Path(tmp)
        limits_dir = tmp_path / "limits"
        limits_dir.mkdir()

        # ------------------------------------------------------------------
        print("\n[1] read-limits — schema real observado em produção")
        fresh = limits_dir / "fresh.json"
        write_limits(fresh, five_hour_pct=9, seven_day_pct=25, age_seconds=5)
        r = run_json(["read-limits", "--path", str(fresh)])
        check("parseia five_hour_used_pct", r.get("five_hour_used_pct") == 9.0, str(r))
        check("parseia seven_day_used_pct", r.get("seven_day_used_pct") == 25.0, str(r))
        check("ok=true para schema válido", r.get("ok") is True)
        check("stale=false para snapshot recém-escrito", r.get("stale") is False)

        print("\n[1b] read-limits — degradação graciosa (nunca lança exceção)")
        missing = limits_dir / "nao-existe.json"
        r = run_json(["read-limits", "--path", str(missing)])
        check("arquivo ausente -> ok=false, error='missing'", r.get("ok") is False and r.get("error") == "missing", str(r))

        malformed = limits_dir / "malformed.json"
        malformed.write_text("{not valid json,,,", encoding="utf-8")
        r = run_json(["read-limits", "--path", str(malformed)])
        check("JSON malformado -> ok=false, error começa com 'malformed'", r.get("ok") is False and str(r.get("error", "")).startswith("malformed"), str(r))

        unexpected = limits_dir / "unexpected.json"
        unexpected.write_text(json.dumps({"updated_at": int(time.time()), "model": "x"}), encoding="utf-8")
        r = run_json(["read-limits", "--path", str(unexpected)])
        check("schema inesperado (sem five_hour/seven_day) -> ok=false", r.get("ok") is False and "unexpected-schema" in str(r.get("error", "")), str(r))

        # ------------------------------------------------------------------
        print("\n[2] record-usage — acumulação com multiplicador + reset automático de ciclo")
        root_ru = tmp_path / "root-record-usage"
        r1 = run_json(["record-usage", "--root", str(root_ru), "--cycle-id", "cycle-A", "--tokens", "100000", "--multiplier", "1.15"])
        check("primeira chamada: 100000*1.15 arredondado p/ cima = 115000", r1.get("self_tracked_tokens_total") == 115000, str(r1))
        r2 = run_json(["record-usage", "--root", str(root_ru), "--cycle-id", "cycle-A", "--tokens", "50000", "--multiplier", "1.15"])
        check("segunda chamada MESMO ciclo acumula (115000 + 57500)", r2.get("self_tracked_tokens_total") == 172500, str(r2))
        r3 = run_json(["record-usage", "--root", str(root_ru), "--cycle-id", "cycle-B", "--tokens", "10000", "--multiplier", "1.15"])
        check("cycle-id NOVO reseta o acumulador antes de somar (não carrega cycle-A)", r3.get("self_tracked_tokens_total") == 11500, str(r3))
        check("--tokens negativo é rejeitado (returncode != 0)", run(["record-usage", "--root", str(root_ru), "--cycle-id", "cycle-B", "--tokens", "-5"]).returncode != 0)

        # ------------------------------------------------------------------
        print("\n[3] check — CASO CENTRAL: snapshot congelado (baixo) + self-tracked alto -> self-tracked vence")
        root_frozen = tmp_path / "root-frozen"
        frozen_low = limits_dir / "frozen-low.json"
        write_limits(frozen_low, five_hour_pct=10, seven_day_pct=20, age_seconds=4000)  # > 900s default stale
        run(["record-usage", "--root", str(root_frozen), "--cycle-id", "cycle-frozen", "--tokens", "255000", "--multiplier", "1.15"])
        r = run_json(["check", "--root", str(root_frozen), "--cycle-id", "cycle-frozen",
                      "--limits-path", str(frozen_low), "--self-tracked-budget-tokens", "300000"])
        check("rate-limit reportado permanece baixo (congelado)", r["rate_limit"]["pct"] == 20.0, str(r))
        check("rate-limit sinalizado como stale (congelado)", r["rate_limit"]["stale"] is True, str(r))
        check("self-tracked pct calculado corretamente (255000*1.15=293250 -> 98%)", r["self_tracked"]["pct"] == 98, str(r))
        check("sinal MAIS FORTE é self-tracked, não rate-limit", r["stronger_signal_source"] == "self-tracked", str(r))
        check("stronger_signal_pct == self_tracked pct (98 > 20)", r["stronger_signal_pct"] == 98, str(r))
        check("veredito = stop (98% >= limiar default 85%)", r["verdict"] == "stop", str(r))

        print("\n[3b] check — inverso: rate-limit fresco ALTO vence quando self-tracked está baixo")
        root_hi = tmp_path / "root-hi"
        fresh_high = limits_dir / "fresh-high.json"
        write_limits(fresh_high, five_hour_pct=92, seven_day_pct=30, age_seconds=5)
        r = run_json(["check", "--root", str(root_hi), "--cycle-id", "cycle-hi", "--limits-path", str(fresh_high)])
        check("sinal mais forte é rate-limit (92% > self-tracked 0%)", r["stronger_signal_source"] == "rate-limit", str(r))
        check("veredito = stop (92% >= 85%)", r["verdict"] == "stop", str(r))

        # ------------------------------------------------------------------
        print("\n[4] check — comparação de limiar sem off-by-one")
        root_edge = tmp_path / "root-edge"
        edge = limits_dir / "edge.json"
        write_limits(edge, five_hour_pct=85.0, seven_day_pct=10, age_seconds=5)
        r = run_json(["check", "--root", str(root_edge), "--cycle-id", "c-edge", "--limits-path", str(edge), "--threshold-pct", "85.0"])
        check("pct == threshold exatamente -> stop (>=, não >)", r["verdict"] == "stop", str(r))
        r = run_json(["check", "--root", str(root_edge), "--cycle-id", "c-edge2", "--limits-path", str(edge), "--threshold-pct", "85.01"])
        check("pct just abaixo do threshold -> start", r["verdict"] == "start", str(r))

        # ------------------------------------------------------------------
        print("\n[5] check --stop-diario grava 'parei-por-cota' via mecanismo append-diario de E8.2")
        root_diario = tmp_path / "root-diario"
        r = run_json(["check", "--root", str(root_diario), "--cycle-id", "c-diario",
                      "--limits-path", str(fresh_high), "--stop-diario"])
        check("diario_recorded=true quando veredito=stop e --stop-diario passado", r.get("diario_recorded") is True, str(r))
        diario_md = (root_diario / "diario.md").read_text(encoding="utf-8")
        check("diario.md contém 'parei-por-cota'", "parei-por-cota" in diario_md, diario_md)
        diario_jsonl_lines = (root_diario / "diario.jsonl").read_text(encoding="utf-8").strip().splitlines()
        jsonl_obj = json.loads(diario_jsonl_lines[-1])
        check("diario.jsonl: event='parei', cycle_id correto", jsonl_obj.get("event") == "parei" and jsonl_obj.get("cycle_id") == "c-diario", str(jsonl_obj))

        root_no_stop = tmp_path / "root-no-stop"
        r = run_json(["check", "--root", str(root_no_stop), "--cycle-id", "c-no-stop", "--limits-path", str(fresh)])
        check("--stop-diario omitido -> diario_recorded=false mesmo com verdict=start (não escreve)", r.get("diario_recorded") is False)
        check("nenhum diario.md criado quando não solicitado", not (root_no_stop / "diario.md").exists())

        # ------------------------------------------------------------------
        print("\n[6] Precedência de config: CLI > env var > quota.config.json > default")
        root_cfg = tmp_path / "root-cfg"
        root_cfg.mkdir()
        (root_cfg / "quota.config.json").write_text(json.dumps({"threshold_pct": 50.0}), encoding="utf-8")
        r = run_json(["check", "--root", str(root_cfg), "--cycle-id", "c-cfg", "--limits-path", str(fresh)])
        check("sem CLI/env: usa quota.config.json (50.0)", r["threshold_pct"] == 50.0, str(r))
        r = run_json(["check", "--root", str(root_cfg), "--cycle-id", "c-cfg", "--limits-path", str(fresh)],
                     env={"GERENTE_QUOTA_THRESHOLD_PCT": "60"})
        check("env var vence o config file (60 > 50 do arquivo)", r["threshold_pct"] == 60.0, str(r))
        r = run_json(["check", "--root", str(root_cfg), "--cycle-id", "c-cfg", "--limits-path", str(fresh), "--threshold-pct", "70"],
                     env={"GERENTE_QUOTA_THRESHOLD_PCT": "60"})
        check("flag de CLI vence env var e config file (70)", r["threshold_pct"] == 70.0, str(r))
        r = run_json(["check", "--root", str(tmp_path / "root-no-config"), "--cycle-id", "c-nc", "--limits-path", str(fresh)])
        check("sem nada: usa o default hardcoded (85.0)", r["threshold_pct"] == 85.0, str(r))

        # ------------------------------------------------------------------
        print("\n[7] Primeiro ciclo de sempre — sem rate-limit, sem self-tracked -> start, não falso-stop")
        root_first = tmp_path / "root-first-ever"
        r = run_json(["check", "--root", str(root_first), "--cycle-id", "c-first", "--limits-path", str(missing)])
        check("rate-limit ausente sinaliza degraded=true", r["rate_limit"]["degraded"] is True, str(r))
        check("mas NÃO é tratado como 100% -- veredito = start", r["verdict"] == "start", str(r))
        check("self-tracked também zerado (ciclo nunca visto)", r["self_tracked"]["tokens_total"] == 0, str(r))

        # ------------------------------------------------------------------
        print("\n[8] E19.2 — cota não fica cega no meio da árvore (estimativa de despacho in-flight)")

        def write_dispatch(root: Path, dispatch_id: str, cycle_id: str, age_seconds: float, done: bool = False) -> None:
            ddir = root / "dispatches" / dispatch_id
            ddir.mkdir(parents=True, exist_ok=True)
            opened_at = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(time.time() - age_seconds))
            (ddir / "request.yaml").write_text(
                f'schema_version: "1"\ndispatch_id: "{dispatch_id}"\nopened_at: "{opened_at}"\ncycle_id: "{cycle_id}"\n',
                encoding="utf-8",
            )
            if done:
                (ddir / "DONE.marker").write_text("", encoding="utf-8")

        # Baseline: 100000*1.15 = 115000 registrados (38% de 300000) -> sozinho seria START.
        root_if = tmp_path / "root-inflight"
        run(["record-usage", "--root", str(root_if), "--cycle-id", "cycle-if", "--tokens", "100000", "--multiplier", "1.15"])
        r = run_json(["check", "--root", str(root_if), "--cycle-id", "cycle-if", "--limits-path", str(fresh)])
        check("sem despacho aberto: só os 115000 registrados -> start", r["verdict"] == "start" and r["self_tracked"]["inflight_dispatches_counted"] == 0, str(r))

        # (a) Despacho ABERTO além da graça (700s > 600) do MESMO ciclo -> +200000 -> stop.
        write_dispatch(root_if, "disp-old", "cycle-if", age_seconds=700)
        r = run_json(["check", "--root", str(root_if), "--cycle-id", "cycle-if", "--limits-path", str(fresh)])
        check("despacho aberto além da graça é CONTADO (count=1)", r["self_tracked"]["inflight_dispatches_counted"] == 1, str(r))
        check("estimativa in-flight somada (200000)", r["self_tracked"]["inflight_estimate_tokens"] == 200000, str(r))
        check("115000 registrados + 200000 estimados cruza o limiar -> stop (fecha a cegueira)", r["verdict"] == "stop", str(r))
        check("recorded_tokens preserva só o durável (115000, sem a estimativa)", r["self_tracked"]["recorded_tokens"] == 115000, str(r))

        # (b) O MESMO despacho, mas DENTRO da graça (60s < 600) -> NÃO conta -> volta a start.
        root_grace = tmp_path / "root-grace"
        run(["record-usage", "--root", str(root_grace), "--cycle-id", "cycle-g", "--tokens", "100000", "--multiplier", "1.15"])
        write_dispatch(root_grace, "disp-fresh", "cycle-g", age_seconds=60)
        r = run_json(["check", "--root", str(root_grace), "--cycle-id", "cycle-g", "--limits-path", str(fresh)])
        check("despacho recém-aberto (dentro da graça) NÃO é contado -> não falso-aborta", r["self_tracked"]["inflight_dispatches_counted"] == 0 and r["self_tracked"]["inflight_dispatches_within_grace"] == 1, str(r))
        check("dentro da graça -> verdict volta a start", r["verdict"] == "start", str(r))

        # (c) Despacho de OUTRO ciclo (além da graça) -> não conta na cota deste ciclo.
        root_oc = tmp_path / "root-othercycle"
        run(["record-usage", "--root", str(root_oc), "--cycle-id", "cycle-now", "--tokens", "100000", "--multiplier", "1.15"])
        write_dispatch(root_oc, "disp-other", "cycle-ANTIGO", age_seconds=700)
        r = run_json(["check", "--root", str(root_oc), "--cycle-id", "cycle-now", "--limits-path", str(fresh)])
        check("despacho de outro ciclo NÃO conta (cota é por-ciclo)", r["self_tracked"]["inflight_dispatches_counted"] == 0 and r["verdict"] == "start", str(r))

        # (d) Despacho FECHADO (DONE.marker presente) além da graça -> não conta.
        root_done = tmp_path / "root-done"
        run(["record-usage", "--root", str(root_done), "--cycle-id", "cycle-d", "--tokens", "100000", "--multiplier", "1.15"])
        write_dispatch(root_done, "disp-closed", "cycle-d", age_seconds=700, done=True)
        r = run_json(["check", "--root", str(root_done), "--cycle-id", "cycle-d", "--limits-path", str(fresh)])
        check("despacho fechado (DONE.marker) NÃO conta -> start", r["self_tracked"]["inflight_dispatches_counted"] == 0 and r["verdict"] == "start", str(r))

        # (e) Estimativa desligada (--per-dispatch-inflight-estimate-tokens 0) -> conta 0 tokens.
        r = run_json(["check", "--root", str(root_if), "--cycle-id", "cycle-if", "--limits-path", str(fresh), "--per-dispatch-inflight-estimate-tokens", "0"])
        check("estimativa 0 desliga a inflação (mesmo com despacho aberto) -> start", r["self_tracked"]["inflight_estimate_tokens"] == 0 and r["verdict"] == "start", str(r))

        # ------------------------------------------------------------------
        print("\n[9] Kill-switch do guardrail (flag enabled) — decisão do dono 2026-07-14")
        # Cenário que NATURALMENTE daria stop: self-tracked alto (293250 -> 98%).
        root_ks = tmp_path / "root-killswitch"
        run(["record-usage", "--root", str(root_ks), "--cycle-id", "cycle-ks", "--tokens", "255000", "--multiplier", "1.15"])
        # Ligado (default): stop.
        r = run_json(["check", "--root", str(root_ks), "--cycle-id", "cycle-ks", "--limits-path", str(frozen_low), "--self-tracked-budget-tokens", "300000"])
        check("guardrail ligado (default): 98% -> stop", r["verdict"] == "stop" and r["guardrail_enabled"] is True, str(r))
        # Desligado via config file enabled=false: força start, mas reporta natural_verdict=stop.
        (root_ks / "quota.config.json").write_text(json.dumps({"enabled": False}), encoding="utf-8")
        r = run_json(["check", "--root", str(root_ks), "--cycle-id", "cycle-ks", "--limits-path", str(frozen_low), "--self-tracked-budget-tokens", "300000"])
        check("enabled=false no config: veredito FORÇADO a start", r["verdict"] == "start", str(r))
        check("enabled=false: guardrail_enabled=false reportado", r["guardrail_enabled"] is False, str(r))
        check("enabled=false: natural_verdict preserva o que SERIA (stop) para diagnóstico", r["natural_verdict"] == "stop", str(r))
        check("enabled=false: reasoning avisa DESLIGADO", "DESLIGADO" in r["reasoning"], str(r))
        # CLI --no-enabled vence o config (que aqui está ausente -> default true).
        r = run_json(["check", "--root", str(tmp_path / "root-ks2"), "--cycle-id", "c", "--limits-path", str(frozen_low), "--self-tracked-budget-tokens", "300000", "--no-enabled"])
        check("--no-enabled na CLI força start", r["verdict"] == "start" and r["guardrail_enabled"] is False, str(r))
        # Env var desliga.
        r = run_json(["check", "--root", str(tmp_path / "root-ks3"), "--cycle-id", "c", "--limits-path", str(frozen_low), "--self-tracked-budget-tokens", "300000"],
                     env={"GERENTE_QUOTA_ENABLED": "false"})
        check("GERENTE_QUOTA_ENABLED=false desliga via env", r["verdict"] == "start" and r["guardrail_enabled"] is False, str(r))

    print(f"\n{'='*60}\nPASS: {len(PASS)}  FAIL: {len(FAIL)}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
