import shared
import os
import soundfile as sf

class GraniteSpeech4p1x2B(shared.SimpleASRModel):
    def __init__(self, state: shared.ModelLoadingState):
        super().__init__(state)
        model_path = f"{state.model_dir}granite-speech-4.1-2b"
        if not os.path.exists(model_path):
            if not state.ask_allow_or_deny(f"Could not find \"{model_path}\". Allow fetching from \"https://huggingface.co/ibm-granite/granite-speech-4.1-2b\"?"):
                state.quit()
            state.show_spinner()
            state.settext("Downloading granite-speech-4.1-2b...")
            from huggingface_hub import snapshot_download
            state.checkpoints.ignore()
            snapshot_download(
                repo_id="ibm-granite/granite-speech-4.1-2b",
                local_dir=model_path,
            )
            state.checkpoints.checkpoint("downloading model")
        state.show_spinner()
        state.checkpoints.checkpoint("preload pytorch")
        state.load_and_check_torch()
        state.checkpoints.checkpoint("loading pytorch")
        import torch
        from transformers import (
            AutoProcessor,
            AutoModelForSpeechSeq2Seq,
        )
        state.checkpoints.checkpoint("reimports")
        print("Loading model...")
        state.settext("Loading granite-speech-4.1-2b...")
        if not torch.cuda.is_available() and not state.allow_cpu:
            state.show_cpu_warning()
        self.device = (
            "cuda"
            if torch.cuda.is_available()
            else "cpu"
        )
        state.settext("Loading granite-speech-4.1-2b (P)...")
        print("Loading processor")
        self.processor = AutoProcessor.from_pretrained(
            model_path,
            local_files_only=True,
        )
        state.checkpoints.checkpoint("loading processor")
        state.settext("Loading granite-speech-4.1-2b (M)...")
        print("Loading model...")
        self.model = AutoModelForSpeechSeq2Seq.from_pretrained(
            model_path,
            local_files_only=True,
            torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
        ).to(self.device)
        state.checkpoints.checkpoint("loading model")
        self._default_prompt = state.prompt.strip()
        if len(state.model_keywords) > 0:
            self.keywords = "Keywords: " + ", ".join(state.model_keywords)
            self._default_prompt += "\n"
            self._default_prompt += self.keywords
        self.prompt = self._default_prompt

    def transcribe(self, file: str) -> str:
        import torch
        wav, sr = sf.read(file) # type: ignore
        if len(wav.shape) > 1:
            wav = wav.mean(axis=1)  # stereo -> mono

        wav = torch.tensor(wav, dtype=torch.float32)
        tokenizer = self.processor.tokenizer
        prompt = tokenizer.apply_chat_template(
            [
                {
                    "role": "user",
                    "content": self.prompt
                }
            ],
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = self.processor(
            prompt,
            wav,
            return_tensors="pt",
        ).to(self.device)
        output = self.model.generate(
            **inputs,
            do_sample=False,
            num_beams=1,
            max_new_tokens=200,
        )
        prompt_len = inputs["input_ids"].shape[-1]
        return tokenizer.batch_decode(
            output[:, prompt_len:],
            skip_special_tokens=True,
        )[0]

    def supports_prompting(self):
        return True

    def default_prompt(self) -> str:
        return self._default_prompt
    
    def set_prompt(self, prompt: str):
        self.prompt = prompt