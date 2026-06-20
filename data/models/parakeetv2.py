import shared
import os

class ParakeetV2(shared.SimpleASRModel):
    def __init__(self, state: shared.ModelLoadingState):
        super().__init__(state)
        model_path = f"{state.model_dir}parakeet-tdt-0.6b-v2.nemo"
        if not os.path.exists(model_path):
            state.hide_spinner()
            if not state.ask_allow_or_deny(f"Could not find \"{model_path}\". Allow fetching from \"https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2\"?"):
                state.quit()
            state.show_spinner()
            state.settext("Downloading parakeet-tdt-0.6b-v2.nemo...")
            from huggingface_hub import hf_hub_download
            state.checkpoints.ignore()
            hf_hub_download(
                repo_id="nvidia/parakeet-tdt-0.6b-v2",
                filename="parakeet-tdt-0.6b-v2.nemo",
                local_dir=model_path,
                local_dir_use_symlinks=False
                )
            state.checkpoints.checkpoint("downloading model")
        state.show_spinner()
        state.checkpoints.checkpoint("preload pytorch")
        state.load_and_check_torch()
        state.checkpoints.checkpoint("loading pytorch")
        print("Initalizing nemo...")
        state.settext("Initalizing nemo...")
        import nemo.collections.asr as nemo_asr
        state.checkpoints.checkpoint("loading nemo_asr")
        print("Initialized.")
        state.settext("Loading parakeet-tdt-0.6b-v2.nemo...")
        self.asr_model = nemo_asr.models.ASRModel.restore_from(model_path) # type: ignore
        state.checkpoints.checkpoint("loading model")
        self.device = next(self.asr_model.parameters()).device # type: ignore
        print(f"Model device: {self.device}")
        if self.device.type == "cpu" and not state.allow_cpu:
            state.show_cpu_warning()
    
    def transcribe(self, file: str) -> str:
        return self.asr_model.transcribe([file])[0].text # type: ignore