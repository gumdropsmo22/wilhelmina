class Colour:
    def __init__(self, value: int):
        self.value = value


class Embed:
    def __init__(self, *, color: int = 0, description: str | None = None, title: str | None = None):
        self.colour = Colour(color)
        self.description = description
        self.title = title
        self.author = None
        self.footer = None
        self.fields = []
        self.timestamp = None

    def set_author(self, name: str = "", icon_url: str = ""):
        self.author = {"name": name, "icon_url": icon_url}

    def set_footer(self, text: str = "", icon_url: str = ""):
        self.footer = {"text": text, "icon_url": icon_url}

    def add_field(self, name: str, value: str, inline: bool = False):
        self.fields.append({"name": name, "value": value, "inline": inline})


class Interaction:
    class Response:
        async def send_message(self, *args, **kwargs):
            pass

    response = Response()


class app_commands:
    class Range(int):
        def __class_getitem__(cls, item):
            return cls

    @staticmethod
    def command(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

    @staticmethod
    def describe(**kwargs):
        def decorator(func):
            return func
        return decorator

