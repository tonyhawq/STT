import shared
import os
import typing
MODEL = None
TOKENIZER = None

def on_load(state: shared.PluginLoadingState):
    state.settext("Loading transformers.AutoTokenizer and AutoModelForCausalLM")
    from transformers import AutoTokenizer, AutoModelForCausalLM
    import torch
    global MODEL
    global TOKENIZER
    state.show_spinner()
    state.settext("Loading Qwen 2.5 1.5B...")
    model_path = shared.get_model_path().removesuffix("/").removesuffix("\\") + "/Qwen2.5-1.5B-Instruct"
    if not os.path.exists(model_path):
        state.hide_spinner()
        if not state.ask_allow_or_deny(f"Could not find \"{model_path}\". Allow fetching from \"https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct\"?"):
                state.quit()
        state.show_spinner()
        state.settext("Downloading Qwen2.5-1.5B-Instruct...")
        from huggingface_hub import snapshot_download
        snapshot_download(
            repo_id="Qwen/Qwen2.5-1.5B-Instruct",
            local_dir=model_path,
        )
    state.settext("Loading Qwen 2.5 1.5B (AT)...")
    TOKENIZER = AutoTokenizer.from_pretrained(
        model_path,
        local_files_only=True
    )
    state.settext("Loading Qwen 2.5 1.5B (AM)...")
    MODEL = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.float16,
        local_files_only=True
    ).to("cuda")
    state.settext("Loaded Qwen.")

def process(input: str, args: dict[str, typing.Any]) -> str:
    if TOKENIZER is None or MODEL is None:
        raise RuntimeError("Attempted to call process on qwen_postprocess while MODEL or TOKENIZER was None.")
    prompt = args.get("prompt")
    if prompt is None:
        raise RuntimeError("Enabled qwen_postprocess without providing a prompt.")
    if not isinstance(prompt, str):
        raise RuntimeError("Enabled qwen_postprocess and provided a prompt that wasn't a string.")
    messages = [
        {
            "role": "system",
            "content": prompt,
        },
        {
            "role": "user",
            "content": f"Transcript: {input}",
        },
    ]

    text = TOKENIZER.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )

    inputs = TOKENIZER(
        text,
        return_tensors="pt",
    ).to(MODEL.device)
    
    output = MODEL.generate(
        **inputs,
        max_new_tokens=max(8, len(input.split()) * 3),
        do_sample=False,
        temperature=None,
        top_p=None,
    )
    result = TOKENIZER.decode(
        output[0][inputs.input_ids.shape[1]:],
        skip_special_tokens=True,
    )
    return result.strip()