class OpenAI:
    class Responses:
        def create(self, *args, **kwargs):
            class Resp:
                output_text = ""
            return Resp()

    def __init__(self):
        self.responses = self.Responses()
