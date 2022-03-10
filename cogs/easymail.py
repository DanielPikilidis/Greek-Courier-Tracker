import discord
from bs4 import BeautifulSoup as bs
from discord.ext import commands, tasks
from requests import get
from json import dump
from os.path import relpath


class EasyMail(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.update_ids.start()
        self.colour = 0x712E7E
        
    @commands.group(name="easymail", invoke_without_command=True)
    async def easymail(self, ctx: commands.Context):
        embed = discord.Embed(
            title="EasyMail help",
            description="All the available subcommands for EasyMail.",
            color=self.colour
        )

        embed.add_field(name="?/easymail track <id1> <id2> ...", value="Returns current status for the package(s)", inline=False)
        embed.add_field(name="?/easymail add <id> <description>", value="Adds the id to the list.", inline=False)
        embed.add_field(name="?/easymail edit <id> <new description>", value = "Replaces the old description with the new.", inline=False)
        embed.add_field(name="?/easymail remove <id>", value="Removed the id from the list.", inline=False)

        embed.set_footer(text=f"easymail help requested by: {ctx.author.display_name}")
        await ctx.send(embed=embed)

    @easymail.command(name="track")
    async def track(self, ctx: commands.Context, *, args):
        for id in args.split():
            await self.send_status(ctx, id, False)

    @easymail.command(name="add")
    async def add(self, ctx: commands.Context, *, args):
        args = args.split()
        id = args[0]
        description = " ".join(args[1:])
        await self.store_id(ctx, id, description)

    @easymail.command(name="edit")
    async def edit(self, ctx: commands.Context, *, args):
        args = args.split()
        id = args[0]
        description = " ".join(args[1:])
        await self.remove_id(ctx, id)
        await self.store_id(ctx, id, description)

    @easymail.command(name="remove")
    async def remove(self, ctx: commands.Context, *, args):
        for id in args.split():
            await self.remove_id(ctx, id)

    ########### ERROR HANDLING ###########

    @track.error
    async def track_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Missing tracking id(s).")

    @add.error
    async def add_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Missing arguments.")

    @edit.error
    async def edit_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Missing arguments.")

    @remove.error
    async def remove_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Missing tracking id.")

    ########### HELPER FUNCTIONS ###########

    async def send_status(self, ctx: commands.Context, id, silent, description=None):
        (result, status) = await self.get_last_status(id)
        if result == 1:
            if not silent:
                await ctx.send(f"package ({id}) not found")
            return

        if description:
            title = description
        else:
            title = id

        embed = discord.Embed(
            title=title,
            url=f"https://trackntrace.easymail.gr/{id}",
            color=self.colour
        )

        embed.add_field(name="Location", value=status['location'], inline=True)
        embed.add_field(name="Description", value=status['description'], inline=True)
        embed.add_field(name="Date", value=status['date'], inline=False)

        await ctx.send(embed=embed)

    async def get_last_status(self, id) -> tuple:
        html = get(f"https://trackntrace.easymail.gr/{id}").text

        soup = bs(html, features="html.parser")
        if soup.find("div", {"class": "cus-alert"}):
            return (1, None)

        current = soup.find_all("tbody")[-1]
        last = current.contents[1]
        items = last.find_all("td")

        return (0, {
            "date": items[0].contents[0],
            "description": items[1].contents[0].capitalize(),
            "location": items[2].contents[0].contents[0].capitalize(),
            "delivered": items[1].contents[0] == "Παραδόθηκε"
        })

    async def store_id(self, ctx: commands.Context, id, description):
        (result, status) = await self.get_last_status(id)
        if result == 1:
            await ctx.send(f"package ({id}) not found")
            return

        if status["delivered"]:
            await ctx.send("package already delivered")
            await self.send_status(ctx, id, False)
            return
        
        if not next((i for i in self.bot.guild_data[str(ctx.guild.id)]['easymail'] if i['id'] == id), None):
            self.bot.guild_data[str(ctx.guild.id)]['easymail'].append({"id": id, "description": description, "status": status})
            await ctx.send(f"Added {id} ({description}) to the list.")

            with open(relpath("data/guild_data.json"), "w") as file:
                dump(self.bot.guild_data, file, indent=4)
        else:
            await ctx.send("package already in list.\nIf you want to change its description use ?/easymail edit")

    async def remove_id(self, ctx: commands.Context, id):
        package = next((i for i in self.bot.guild_data[str(ctx.guild.id)]['easymail'] if i['id'] == id), None)
        if package:
            description = package['description']
            self.bot.guild_data[str(ctx.guild.id)]['easymail'].remove(package)
            await ctx.send(f"Removed {id} ({description}) from the list")

            with open(relpath("data/guild_data.json"), "w") as file:
                dump(self.bot.guild_data, file, indent=4)
        else:
            await ctx.send(f"package {id} is not in the list.")

    async def check_if_changed(self, guild, entry, old_status) -> tuple:
        (result, new) = await self.get_last_status(entry['id'])

        if new['date'] != old_status['date']:
            entry['status'] = new
            if new['delivered']:
                for i in self.bot.guild_data[guild]['easymail']:
                    if i['id'] == entry['id']:
                        self.bot.guild_data[guild]['easymail'].remove(i)

            with open(relpath("data/guild_data.json"), "w") as file:
                dump(self.bot.guild_data, file, indent=4)

            return (True, new)
        return (False, None)

    @tasks.loop(minutes=5.0)
    async def update_ids(self):
        for guild in self.bot.guild_data:
            updates_channel = int(self.bot.guild_data[guild]['updates_channel'])
            if updates_channel == 0:
                continue
            for entry in self.bot.guild_data[guild]['easymail']:
                (result, new) = await self.check_if_changed(guild, entry, entry['status'])
                if result:
                    embed = discord.Embed(
                        title=entry['description'],
                        url=f"https://trackntrace.easymail.gr/{entry['id']}",
                        color=self.colour
                    )
                    embed.add_field(name="Location", value=new['location'], inline=True)
                    embed.add_field(name="Description", value=new['description'], inline=True)
                    embed.add_field(name="Date", value=f"{new['date']}", inline=False)

                    channel = self.bot.get_channel(updates_channel)
                    await channel.send(embed=embed)

                    if new['delivered']:
                        await channel.send(f"Removed {entry['id']} ({entry['description']}) from the list")


def setup(bot: commands.Bot):
    bot.add_cog(EasyMail(bot))