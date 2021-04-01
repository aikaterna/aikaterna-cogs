class RssFeed():
    """RSS feed object"""

    def __init__(self, **kwargs):
        super().__init__()
        self.name: str = kwargs.get("name", None)
        self.last_title: str = kwargs.get("last_title", None)
        self.last_link: str = kwargs.get("last_link", None)
        self.last_time: str = kwargs.get("last_time", None)
        self.template: str = kwargs.get("template", None)
        self.url: str = kwargs.get("url", None)
        self.template_tags: List[str] = kwargs.get("template_tags", [])
        self.is_special: List[str] = kwargs.get("is_special", [])
        self.embed: bool = kwargs.get("embed", True)
        self.embed_color: str = kwargs.get("embed_color", None)
        self.embed_image: str = kwargs.get("embed_image", None)
        self.embed_thumbnail: str = kwargs.get("embed_thumbnail", None)

    def to_json(self) -> dict:
        return {
            "name": self.name,
            "last_title": self.last_title,
            "last_link": self.last_link,
            "last_time": self.last_time,
            "template": self.template,
            "url": self.url,
            "template_tags": self.template_tags,
            "is_special": self.is_special,
            "embed": self.embed,
            "embed_color": self.embed_color,
            "embed_image": self.embed_image,
            "embed_thumbnail": self.embed_thumbnail,
        }

    @classmethod
    def from_json(cls, data: dict):
        return cls(
            name=data["name"] or None,
            last_title=data["last_title"] or None,
            last_link=data["last_link"] or None,
            last_time=data["last_time"] or None,
            template=data["template"] or None,
            url=data["url"] or None,
            template_tags=data["template_tags"] or [],
            is_special=data["is_special"] or [],
            embed=data["embed"] or True,
            embed_color=data["embed_color"] or None,
            embed_image=data["embed_image"] or None,
            embed_thumbnail=data["embed_thumbnail"] or None,
        )
