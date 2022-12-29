import asyncio
import logging
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession, async_sessionmaker

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, JobQueue, Application, ContextTypes

from twitchAPI.twitch import Twitch

from tokens import TELEGRAM_TOKEN, TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET
from database import Base, Streamer, Group, GroupStreamer


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

class StreamerAlertBot:
    __telegram: Application
    __job_queue: JobQueue
    __engine: AsyncEngine
    __async_session: async_sessionmaker[AsyncSession]
    __twitch: Twitch

    def __init__(self):
        self.init_telegram()

    async def post_init(self, application: Application) -> None:
        await asyncio.gather(self.init_db(), self.init_twitch())

    async def init_db(self):
        self.__engine = create_async_engine("sqlite+aiosqlite:///db.sqlite")

        self.__async_session = async_sessionmaker(self.__engine, expire_on_commit=False)

        async with self.__engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def init_twitch(self):
        self.__twitch = await Twitch(app_id=TWITCH_CLIENT_ID, app_secret=TWITCH_CLIENT_SECRET)

    def init_telegram(self):
        self.__telegram = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(self.post_init).post_shutdown(self.stop).build()
        self.__job_queue: JobQueue = self.__telegram.job_queue
        self.__telegram.add_handler(CommandHandler('online', self.online_streamers))
        self.__telegram.add_handler(CommandHandler('add', self.add_streamer))
        self.__telegram.add_handler(CommandHandler('remove', self.remove_streamer))
        self.__telegram.add_handler(CommandHandler('list', self.streamer_list))
        self.__job_queue.run_repeating(self.check_streamer_online, 60.0)

    def start(self):
        self.__telegram.run_polling()

    async def stop(self, _: ContextTypes.DEFAULT_TYPE):
        await self.__engine.dispose()
        await self.__twitch.close()

    async def online_streamers(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        group = await self.get_group(update.effective_chat.id)
        streamers = []

        if group.enabled:
            query = select(Streamer).where(Streamer.id == GroupStreamer.streamer).where(GroupStreamer.group == update.effective_chat.id)

            async with self.__async_session() as session:
                results = await session.execute(query)
                streamers = results.scalars().all()

        msg_to_send: str

        if len(list(filter(lambda x: x.online, streamers))) > 0:
            msg_to_send = "Streamers online:"
            for streamer in streamers:
                if streamer.online:
                    msg_to_send += f"\n\t<a href=\"{streamer.url}\">{streamer.name}</a>"
        else:
            msg_to_send = "No streamers online"

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=msg_to_send,
            disable_web_page_preview=True,
            parse_mode="HTML"
        )

    async def add_streamer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        group = await self.get_group(update.effective_chat.id)

        new_streamers = []
        not_found = []

        for streamer_id in context.args:
            try:
                streamer = await self.get_or_create_streamer(streamer_id)
            except:
                not_found.append(streamer_id)
                continue

            async with self.__async_session() as session:
                streamer_in_group = await session.get(GroupStreamer, {"group": group.id, "streamer": streamer.id})
                if streamer_in_group:
                    continue

                session.add(GroupStreamer(group=group.id, streamer=streamer.id))
                await session.commit()

            new_streamers.append(streamer.name)

        if len(new_streamers) > 0:
            async with self.__async_session() as session:
                group_to_update = await session.get(Group, group.id)
                group_to_update.enabled = True
                await session.commit()

        added_msg = "Added:\n" + "\n".join(new_streamers) if len(new_streamers) > 0 else "No new streamers added to the list.\n"
        error_msg = "Not found:\n" + "\n".join(not_found) if len(not_found) > 0 else ""

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=added_msg + error_msg
        )

    async def remove_streamer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        group = await self.get_group(update.effective_chat.id)

        removed_streamers = []
        not_found = []
        not_registered = []

        for streamer_id in context.args:
            try:
                streamer = await self.get_or_create_streamer(streamer_id)
            except:
                not_found.append(streamer_id)
                continue

            async with self.__async_session() as session:

                streamer_in_group: GroupStreamer = await session.get(GroupStreamer, {"group": group.id, "streamer": streamer.id})
                if not streamer_in_group:
                    not_registered.append(streamer_id)
                    continue

                removed_streamers.append(streamer.name)
                await session.delete(streamer_in_group)
                await session.commit()

        async with self.__async_session() as session:
            streamers_in_group = await session.execute(select(GroupStreamer).filter_by(group=group.id))
            if len(streamers_in_group.scalars().all()) == 0:
                group_to_update = session.get(Group, group.id)
                group_to_update.enabled = False
            await session.commit()

        removed_msg = "Removed:\n" + "\n".join(removed_streamers) if len(removed_streamers) > 0 else "No streamers removed from the list.\n"
        not_registered_msg = "Not previously on the list:\n" + "\n".join(not_registered) if len(not_registered) else ""
        error_msg = "Not found:\n" + "\n".join(not_found) if len(not_found) > 0 else ""

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=removed_msg + not_registered_msg + error_msg
        )

    async def streamer_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):

        group = await self.get_group(update.effective_chat.id)

        streamers: List[Streamer]
        async with self.__async_session() as session:
            results = await session.execute(
                select(Streamer)
                .where(Streamer.id == GroupStreamer.streamer)
                .where(GroupStreamer.group == group.id)
            )
            streamers = results.scalars().all()

        msg_text: str

        if len(streamers) > 0:
            msg_text = "Streamers:"
            for streamer in streamers:
                msg_text += f"\n\t<a href=\"{streamer.url}\">{streamer.name}</a>: " + ("🔴" if streamer.online else "<i>offline</i>")
        else:
            msg_text = "No streamers configured"

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=msg_text,
            disable_web_page_preview=True,
            parse_mode="HTML"
        )

    async def check_streamer_online(self, context: ContextTypes.DEFAULT_TYPE):

        async with self.__async_session() as session:
            results = await session.execute(
                select(Streamer)
                .where(Streamer.id == GroupStreamer.streamer and GroupStreamer.group == Group.id and Group.enabled == True)
            )

            streamers_to_check: List[Streamer] = results.scalars().all()

            if len(streamers_to_check) == 0:
                return

            ids_of_streamers_to_check = {streamer.id: streamer for streamer in streamers_to_check}
            streamers_checked = []

            async for stream in self.__twitch.get_streams(user_id=[streamer_to_check.id for streamer_to_check in streamers_to_check]):
                streamer: Streamer = ids_of_streamers_to_check[stream.user_id]
                streamers_checked.append(streamer.id)
                if not streamer.online:
                    streamer.online = True
                    groups = await session.execute(select(GroupStreamer.group).filter_by(streamer=streamer.id))
                    for group in groups.scalars():
                        await context.bot.send_message(
                            chat_id=group,
                            text=f"<a href=\"{streamer.url}\">{streamer.name}</a> is online.\n{stream.title}",
                            parse_mode="HTML"
                        )

            # Mark offline streamers
            for streamer in streamers_to_check:
                if streamer.id not in streamers_checked:
                    streamer.online = False

            await session.commit()

    async def get_or_create_streamer(self, streamer_id: str) -> Streamer:

        async for user in self.__twitch.get_users(logins=[streamer_id]):
            async with self.__async_session() as session:

                streamer = await session.get(Streamer, user.id)
                if not streamer:
                    streamer = Streamer(id=user.id, name=user.display_name, login=user.login)
                    session.add(streamer)
                    await session.commit()

                return streamer
        raise Exception("No user found")

    async def get_group(self, group_id: int) -> Group:
        async with self.__async_session() as session:

            group = await session.get(Group, group_id)
            if not group:
                group = Group(id=group_id, enabled=False)
                session.add(group)
                await session.commit()
            return group


if __name__ == '__main__':
    bot = StreamerAlertBot()
    bot.start()
