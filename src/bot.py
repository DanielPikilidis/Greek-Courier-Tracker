import discord, logging, sqlite3
from discord.ext import commands
from logging.handlers import TimedRotatingFileHandler
from os import listdir, makedirs
from os.path import relpath, exists
from json import loads, dump
from sys import stdout
from os import getenv
from logging.config import dictConfig

from log_config import LogConfig
import sqlite3_handler

class Main(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.started = False
        
    @commands.Cog.listener()
    async def on_ready(self):
        if not self.started:
            for filename in listdir("./cogs"):
                if filename.endswith(".py"):
                    try:
                        self.bot.load_extension(f"cogs.{filename[:-3]}")
                        self.bot.logger.info(f"Loaded cog: {filename[:-3]}")
                    except:
                        self.bot.logger.warning(f"Failed to load cog: {filename[:-3]}")

            self.started = True
            self.bot.logger.info(f"Bot logged in and ready. Joined guilds: {len(bot.guilds)}")

        await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="?/help"))

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        self.bot.logger.info(f"Joined guild {guild.id}")
        sqlite3_handler.insert_guild(guild.id)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        self.bot.logger.info(f"Left guild {guild.id}")
        sqlite3_handler.delete_guild(guild.id)

    @commands.command(name="help")
    async def help(self, ctx: commands.Context):
        embed = discord.Embed(
            title="Help",
            description="All the available commands.",
            color=0xFFFFFF
        )

        for courier in self.bot.cogs:
            if courier == "Main":
                continue
            embed.add_field(name=courier.lower(), value=f"Returns available commands for {courier}", inline=False)


        if not self.bot.guild_data[str(ctx.guild.id)]["updates_channel"]:
            embed.add_field(
                name="?/updates <#channel>",
                value = "Sets the channel to send updates when a parcel updates.\n"
                        "A channel for updates has not been set, so no updates will be sent!",
                inline=False
            )
        else:
            embed.add_field(
                name="?/updates <#channel>",
                value="Sets the channel to send updates when a parcel updates",
                inline=False
            )

        embed.add_field(
            name="?/track <id>",
            value="Figures out the correct courier and returns the parcel status.",
            inline=False
        )

        embed.set_footer(text=f"Help requested by: {ctx.author.display_name}")
        await ctx.send(embed=embed)

    @commands.command(name="updates")
    async def updates(self, ctx: commands.Context, arg1):
        channel = self.bot.get_channel(int(arg1[2:-1]))
        if channel is None:
            await ctx.send("Invalid channel.")
            return

        sqlite3_handler.update_channel(ctx.guild.id, str(channel.id))
        await ctx.send("Updates channel changed.")

    @updates.error
    async def updates_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Missing channel argument.")

    @commands.command(name="track")
    async def track(self, ctx: commands.Context, arg1):
        # This is not a good solution and needs to be changed / improved.
        id = arg1
        if len(id) == 10:
            couriers = [self.bot.get_cog("ACS"), self.bot.get_cog("Geniki")]
            for courier in couriers:
                await courier.__track_id(ctx, id, True)
        elif len(id) == 11:
            courier = self.bot.get_cog("EasyMail")
            await courier.__track_id(ctx, id, True)
        elif len(id) == 12:
            couriers = [self.bot.get_cog("Speedex"), self.bot.get_cog("Delatolas"), self.bot.get_cog("IKEA")]
            for courier in couriers:
                await courier.__track_id(ctx, id, True)
        elif len(id) == 13:
            couriers = [self.bot.get_cog("ELTA"), self.bot.get_cog("Skroutz")]
            for courier in couriers:
                await courier.__track_id(ctx, id, True)

    @track.error
    async def track_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Missing tracking id.")


def create_database():
    conn = sqlite3.connect("/data/data.sqlite3")
    cur = conn.cursor()

    query = """
    ATTACH DATABASE 'data.sqlite3' AS GuildData;

    CREATE TABLE IF NOT EXISTS Packages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tracking_id TEXT,
        courier_name TEXT,
        description TEXT,
        last_location TEXT,
        guild_id TEXT,
        FOREIGN KEY (guild_id) REFERENCES Guilds(guild_id)
    );

    CREATE TABLE IF NOT EXISTS Guilds (
        guild_id TEXT PRIMARY KEY,
        updates_channel TEXT
    );
    """

    cur.executescript(query)
    conn.commit()
    conn.close()
    
    bot.logger.info("Created database.")

def check_database():
    if not exists("/data/data.sqlite3"):
        with open("/data/data.sqlite3", "w") as file:
            pass
        create_database()

def check_config():
    if not exists("/config/config.json"):
        with open("/config/config.json", "w") as file:
            config = {
                "keys": {
                    "discord": "",
                },
            }
            dump(config, file, indent=4)
        print("Paste your key in config.txt file in config/")
        exit(1)

bot = None

def main():
    TRACKER_URL = getenv("TRACKER_URL", "https://courier-api.danielpikilidis.com/")
    dictConfig(LogConfig().dict())

    global bot
    bot = commands.Bot(command_prefix="?/", help_command=None)

    bot.logger = logging.getLogger(getenv("LOG_NAME", "courier-tracking-bot"))

    check_database()
    check_config()

    bot.add_cog(Main(bot))

    with open("/config/config.json", "r") as file:
        config = loads(file.read())
        key = config['keys']['discord']
    bot.run(key)

if __name__ == "__main__":
    main()