import shared
import os
import soundfile as sf

class GraniteSpeech4p1x2B:
    def __init__(self, state: shared.ModelLoadingState):
        self.state = state
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
    
    def transcribe(self, file: str) -> str:
        import torch
        wav, sr = sf.read(file)
        if len(wav.shape) > 1:
            wav = wav.mean(axis=1)  # stereo -> mono

        wav = torch.tensor(wav, dtype=torch.float32)
        tokenizer = self.processor.tokenizer
        prompt = tokenizer.apply_chat_template(
            [
                {
                    "role": "user",
                    "content": """<|audio|>You are a speech-to-text system.
Transcribe the audio into well-formatted written English.
Add punctuation (periods, commas, question marks, exclamation marks) where appropriate.
Capitalize sentences correctly.
This is real-time spoken input. Preserve commands, names, and game-specific terms exactly as spoken.
Output ONLY the final transcription with no explanations.."""
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
            max_new_tokens=256,
        )
        prompt_len = inputs["input_ids"].shape[-1]
        return tokenizer.batch_decode(
            output[:, prompt_len:],
            skip_special_tokens=True,
        )[0]