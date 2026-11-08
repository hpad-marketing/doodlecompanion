"""Orpheus 3B runner (Apache-2.0 model on a Llama 3.2 base, so Meta's licence
also applies; the HF repo is gated, so log in with `hf auth login` once).
Plain transformers + SNAC decoding, no vLLM, so it runs on Windows.
voice = one of tara, leah, jess, leo, dan, mia, zac, zoe. Tags: <laugh> etc."""
import torch
from _common import load_job, seed_all, write_wav
from snac import SNAC
from transformers import AutoModelForCausalLM, AutoTokenizer

REPO = "canopylabs/orpheus-3b-0.1-ft"
job = load_job()
tok = AutoTokenizer.from_pretrained(REPO)
model = AutoModelForCausalLM.from_pretrained(REPO, torch_dtype=torch.bfloat16).to("cuda")
snac = SNAC.from_pretrained("hubertsiuzdak/snac_24khz").to("cuda")


def decode(codes):
    l1, l2, l3 = [], [], []
    for i in range(len(codes) // 7):
        c = codes[7 * i:7 * i + 7]
        l1.append(c[0])
        l2 += [c[1] - 4096, c[4] - 4 * 4096]
        l3 += [c[2] - 2 * 4096, c[3] - 3 * 4096, c[5] - 5 * 4096, c[6] - 6 * 4096]
    t = [torch.tensor(x, device="cuda").unsqueeze(0) for x in (l1, l2, l3)]
    with torch.inference_mode():
        return snac.decode(t).squeeze().float().cpu().numpy()


for line in job["lines"]:
    seed_all(line.get("seed"))
    prompt = f"{line.get('voice') or 'leo'}: {line['text']}"
    ids = tok(prompt, return_tensors="pt").input_ids
    ids = torch.cat([torch.tensor([[128259]]), ids, torch.tensor([[128009, 128260]])], dim=1).to("cuda")
    with torch.inference_mode():
        gen = model.generate(ids, attention_mask=torch.ones_like(ids), max_new_tokens=2400, do_sample=True,
                             temperature=0.6, top_p=0.95, repetition_penalty=1.1, eos_token_id=128258)
    out = gen[0, ids.shape[1]:].tolist()
    if 128257 in out:
        out = out[len(out) - out[::-1].index(128257):]
    codes = [t - 128266 for t in out if t != 128258]
    codes = codes[: len(codes) // 7 * 7]
    write_wav(line["out"], decode(codes), 24000)
