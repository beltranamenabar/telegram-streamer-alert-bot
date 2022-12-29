from sqlalchemy import Integer, String, Boolean, ForeignKey
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped

TWITCH_URL: str = "https://twitch.tv"

# declarative base class
class Base(DeclarativeBase):
    pass

# an example mapping using the base
class Streamer(Base):
    __tablename__ = "streamers"

    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    login: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(60))
    online: Mapped[bool] = mapped_column(Boolean, default=False)

    @hybrid_property
    def url(self):
        return f"{TWITCH_URL}/{self.login}"

class Group(Base):
    __tablename__ = "groups"

    id = mapped_column(Integer, primary_key=True)
    enabled = mapped_column(Boolean, default=False)

    def __repr__(self) -> str:
        return f"<Group id: {self.id}, enabled: {self.enabled}>"

class GroupStreamer(Base):
    __tablename__ = "groups_streamers"

    streamer = mapped_column(ForeignKey(Streamer.id), primary_key=True)
    group = mapped_column(ForeignKey(Group.id), primary_key=True)
