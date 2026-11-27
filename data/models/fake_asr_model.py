import shared
import random

class FakeASRModel(shared.SimpleASRModel):
    def __init__(self, state: shared.ModelLoadingState):
        super().__init__(state)
        self.tid = 0
        self.starters = [
            "The suspicious raccoon",
            "My grandmother's toaster",
            "A surprisingly emotional penguin",
            "The last remaining astronaut",
            "Somewhere beneath the ocean",
            "The government of Mars",
            "An elderly wizard",
            "My neighbor's goldfish",
            "The world's least successful detective",
            "A very confused scientist",
            "Nobody in the village",
            "The ghost of a forgotten king",
            "Every Tuesday morning",
            "A tiny man in a large hat",
            "The international committee of ducks",
            "An ambitious potato",
            "The creature living in my walls",
            "A philosopher with questionable credentials",
            "The ancient prophecy",
            "My sleep-deprived brain",
            "A mysterious stranger",
            "The entire population of Nebraska",
            "A particularly aggressive squirrel",
            "The last person on Earth",
            "An undercover pigeon"
        ]
        self.middles = [
            "has recently developed an unhealthy obsession with",
            "was secretly responsible for",
            "cannot stop thinking about",
            "has been legally forbidden from discussing",
            "accidentally invented",
            "is currently negotiating with",
            "has a complicated relationship with",
            "was deeply disappointed by",
            "is planning to overthrow",
            "has been hiding inside",
            "unexpectedly challenged",
            "refuses to acknowledge",
            "has devoted their entire life to",
            "was caught stealing",
            "is desperately searching for",
            "has finally come to terms with",
            "is preparing a presentation about",
            "was emotionally destroyed by",
            "has been spreading rumors about",
            "is convinced that",
            "recently made a deal with",
            "is attempting to communicate with",
            "has been secretly training for",
            "was deeply offended by",
            "is writing a strongly worded letter to"
        ]
        self.endings = [
            "the inevitable collapse of civilization.",
            "a suspiciously large collection of spoons.",
            "the fact that nobody likes Tuesdays.",
            "an army of highly trained hamsters.",
            "the mysterious disappearance of all the cheese.",
            "a portal to another dimension.",
            "the ancient art of competitive gardening.",
            "a sandwich that knows too much.",
            "the unbearable weight of existence.",
            "a deeply unfortunate misunderstanding.",
            "the secret underground economy of squirrels.",
            "a very expensive emotional support cactus.",
            "the true meaning of breakfast.",
            "an international incident involving mayonnaise.",
            "the moon being made entirely of soup.",
            "a spreadsheet containing everyone's secrets.",
            "the possibility of becoming a professional worm.",
            "an unexplained shortage of left shoes.",
            "the return of the legendary wizard council.",
            "a tiny horse with enormous ambitions.",
            "the complete destruction of the local bakery.",
            "a suspiciously intelligent houseplant.",
            "the fact that birds might be government employees.",
            "an existential crisis at the supermarket.",
            "the world's first underwater disco."
        ]

    def transcribe(self, file: str) -> str:
        self.tid += 1
        return f"{random.choice(self.starters)} {random.choice(self.middles)} {random.choice(self.endings)}"