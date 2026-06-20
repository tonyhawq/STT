import shared

class FakeASRModel(shared.SimpleASRModel):
    def __init__(self, state: shared.ModelLoadingState):
        super().__init__(state)
        self.tid = 0

    def transcribe(self, file: str) -> str:
        self.tid += 1
        return f"Text ({self.tid})"