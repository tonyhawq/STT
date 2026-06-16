import shared

class FakeASRModel:
    def __init__(self, state: shared.ModelLoadingState):
        self.tid = 0

    def transcribe(self, file: str) -> str:
        self.tid += 1
        return f"Text ({self.tid})"