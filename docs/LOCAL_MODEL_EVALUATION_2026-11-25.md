# NEXUS MASTER — local model evaluation (2026-11-25)

## Scope and constraints

This is a research assessment, not a deployment or benchmark report. No model weights were downloaded, no inference server was installed, and no local performance test was run.

Known target hardware: Asus TUF laptop with NVIDIA GTX 1650 4 GB VRAM and an Intel i5 CPU (generation and system RAM not yet verified). The HP/Lenovo mini-PC CPU and RAM specifications are also unknown. Estimates below are therefore capacity screening, not measured performance.

Keep the OpenAI Responses API as the default provider. Local models remain optional specialists behind the existing local OpenAI-compatible adapter. Do not silently route prompts to a local model or enable a remote inference endpoint.

## Candidate comparison

| Model | Publisher-reported size/context | License | GTX 1650 4 GB assessment | NEXUS role |
|---|---|---|---|---|
| LiquidAI LFM3-1.7B | 1.73B parameters; 256K context; publisher documents approximately 1 GB at 4-bit | LFM Open License v1.0 (not Apache/MIT) | Most plausible edge candidate. Q4 weights can fit in the VRAM budget in principle, but runtime/KV cache still matter. Start with a short context and CPU fallback. | Local summarization, telemetry/log explanation, lightweight classification. Not the primary coding or multi-step reasoning agent. |
| Qwen3-4B | 4B class; Qwen3 family supports long context with configuration-dependent trade-offs | Apache-2.0 | Q4 weights are roughly 2–2.5 GB before runtime/KV cache; full-GPU inference is tight at 4 GB. Use partial GPU offload and CPU RAM if available. | Best next general-purpose local candidate after LFM3, pending RAM check and benchmark. |
| DeepSeek-R1-Distill-Qwen-7B | 7B class reasoning distillation | MIT | Q4 weights alone approach/exceed practical 4 GB VRAM once runtime and KV cache are included. CPU offload required. | Optional reasoning specialist on a higher-RAM host; slower than smaller models. |
| Qwen3-8B | 8B class | Apache-2.0 | Q4 weights alone are around 4 GB or more before runtime; not a full-GPU fit on GTX 1650. | Defer until a larger-memory host is available. |
| Qwen3-14B | 14B class | Apache-2.0 | Q4 weights require substantially more than 4 GB; CPU offload would be heavy. | Defer until hardware upgrade or larger mini-PC/server is measured. |
| OpenAI GPT-OSS-20B | 20B class; MXFP4; publisher model card states it can run within 16 GB memory | Apache-2.0 | Not a practical full-GPU fit on 4 GB VRAM. CPU execution requires adequate system RAM and will be slower. | Future local high-capability candidate only after RAM/GPU validation. |

Approximate Q4 weight sizes for Qwen/DeepSeek are parameter-count estimates and exclude KV cache, runtime allocations, context buffers, and quantization metadata. Actual memory use depends on the exact GGUF/AWQ/GPTQ build, context length, batch size, and backend.

## Recommendation and sequence

1. Keep OpenAI Responses API as default and retain LFM3 as an opt-in adapter only.
2. First local proof-of-concept: LFM3-1.7B Q4 on CPU or partial GPU, 4K–8K context, with a small benchmark covering latency, RAM/VRAM, output quality and process isolation.
3. Second candidate: Qwen3-4B Q4 with CPU offload, after confirming laptop RAM and available disk. Compare it against LFM3 on the same prompts.
4. Evaluate DeepSeek-R1-Distill-Qwen-7B only on a host with sufficient RAM; do not attempt to fit it fully into 4 GB VRAM.
5. Defer Qwen3-8B/14B and GPT-OSS-20B until a higher-memory host is measured.

## Existing NEXUS integration status

The optional LFM3 adapter in application/core/PROJECT-NEXUS-LOCAL/app/lfm3_local.py targets an OpenAI-compatible local endpoint. It is gated by explicit configuration; remote HTTPS is separately gated. The adapter does not contain model weights or start an inference server. Its presence is not proof that LFM3 is installed or operational.

## License and security notes

- LFM3 uses the LFM Open License v1.0; review the exact license terms before commercial redistribution or embedding it in a distributed product.
- Qwen3 and GPT-OSS model cards specify Apache-2.0; DeepSeek-R1-Distill-Qwen-7B specifies MIT. Preserve each model's own notices and license text when redistributing.
- Keep inference local by default. Do not expose the local model server to LAN/WAN, do not place model API keys in source code, and do not allow local models to sign wallets, submit mining shares, place exchange orders, or change configuration automatically.
- Model outputs are untrusted research suggestions. Any model-assisted changes to mining, wallet, EDGE, security, or trading settings remain manual-review only.

## Primary model references

- GPT-OSS-20B model card: https://huggingface.co/openai/gpt-oss-20b
- LFM3-1.7B model card: https://huggingface.co/LiquidAI/LFM3-1.7B
- LFM Open License: https://www.liquid.ai/lfm-open-license
- Qwen3-4B: https://huggingface.co/Qwen/Qwen3-4B
- Qwen3-8B: https://huggingface.co/Qwen/Qwen3-8B
- Qwen3-14B: https://huggingface.co/Qwen/Qwen3-14B
- DeepSeek-R1-Distill-Qwen-7B: https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-7B