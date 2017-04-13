import discord
import asyncio
import aiohttp
import ctypes.util
import urllib.parse
from datetime import datetime, timedelta
from io import StringIO
from sys import stdout, stderr

client = discord.Client()
LOG = stderr
NAME = "b3Bot"

commands = {}
players = {}
react_msgs = {}

async def cleanup(messages):
    await asyncio.sleep(30)
    for message in messages:
        await client.delete_message(message)

async def ptpb(text, filename=None):
    with aiohttp.ClientSession() as session:
        data = aiohttp.FormData()
        data.add_field("c", StringIO(text), filename=filename)
        headers = {"Accept": "application/json"}
        async with session.post("https://ptpb.pw", data=data, headers=headers) as resp:
            d = await resp.json()
            return d["url"]

async def is_privileged(member):
    if member.id == "133057442425602048":
        return True
    for role in member.server.roles:
        if role.name == NAME + "User":
            if role in member.roles:
                return True
    return False

async def reply(message, text, rm=0):
    resp = await client.send_message(message.channel, text)
    await cleanup([message, resp][rm:])

def cmd(func):
    commands[func.__name__] = func
    def dec(*args, **kwargs):
        return func(*args, **kwargs)
    return dec

@cmd
async def help(message, *args):
    "Returns this message"
    cmds = sorted(commands.keys())
    if not await is_privileged(message.author):
        cmds = [c for c in cmds if c not in privileged]
    out = "\n".join(["{}: {}".format(cmd, commands[cmd].__doc__) for cmd in cmds])
    await reply(message, "```{}```".format(out))

@cmd
async def sleep(message, *args):
    "Naps for five seconds"
    resp = await client.send_message(message.channel, ":sleeping:")
    await asyncio.sleep(5)
    await client.edit_message(resp, 'Hi there!')
    await cleanup([message, resp])

@cmd
async def invite(message, *args):
    "Returns the link to invite " + NAME + " to your server"
    await reply(message, discord.utils.oauth_url(client.user.id))

@cmd
async def source(message, *args):
    "Returns the source for " + NAME
    with open(__file__) as f:
        source = f.read()
    await client.send_typing(message.channel)
    url = await ptpb(source, file=NAME + ".py")
    await reply(url + "/py")

@cmd
async def react(message, *args):
    "Lets users react!"
    r = 'React with thumbs up or thumbs down.' if not args else " ".join(args)
    msg = await client.send_message(message.channel, r)
    await client.delete_message(message)
    react_msgs[msg.id] = r

@client.event
async def on_reaction_add(reaction, user):
    if reaction.message.id in react_msgs:
        await update_reactions(reaction)

@client.event
async def on_reaction_remove(reaction, user):
    if reaction.message.id in react_msgs:
        await update_reactions(reaction)

async def update_reactions(reaction):
    def rcount(r, name):
        return len([x for x in reaction.message.reactions if x.emoji == name])
    if reaction.message.id in react_msgs:
        await client.edit_message(reaction.message, "{} ({}){}".format(
            react_msgs[reaction.message.id],
            ":white_check_mark:" if rcount(reaction, "👍") > rcount(reaction, "👎")
            else ":negative_squared_cross_mark:",
            " (ended)" if rcount(reaction, "❌") > 0 else ""
        ))
        if reaction.emoji == "❌":
            del react_msgs[reaction.message.id]

@cmd
async def vjoin(message, *args):
    "Tells " + NAME + " to join a voice channel"
    if not await is_privileged(message.author):
        await reply(message, "You can't perform this action")
        return
    if not discord.opus.is_loaded():
        discord.opus.load_opus(ctypes.util.find_library("opus"))
    if not message.server:
        return
    channels = {channel.name: channel for channel in message.server.channels if channel.type is discord.ChannelType.voice}
    if not channels:
        await reply(message, "No voice channels")
    else:
        if args:
            dest = channels[args[0]] if channels and args[0] in channels else None
            vc = client.voice_client_in(message.server)
            if vc:
                await vc.move_to(dest)
            else:
                await client.join_voice_channel(dest)
            await reply(message, "Joined " + dest.name)
        else:
            await reply(message, "Choose one of: " + ", ".join(channels.keys()))

@cmd
async def vpart(message, *args):
    "Tells " + NAME + " to leave the connected voice channel"
    if not await is_privileged(message.author):
        await reply(message, "You can't perform this action")
        return
    await client.voice_client_in(message.server).disconnect()
    await reply(message, "Disconnected from voice channel")

@cmd
async def yt(message, *args):
    "Starts playing a given youtube video or search result"
    if not client.is_voice_connected(message.server):
        await reply(message, "Use !voice to join a voice channel")
        return
    vc = client.voice_client_in(message.server)
    ytdl_opts = None
    if len(args) == 0:
        url = "https://youtu.be/dQw4w9WgXcQ"
    elif len(args) == 1 and len(args[0]) == 11:
        url = "https://youtu.be/" + args[0]
    else:
        ytdl_opts = {"playlistend": 1}
        url = "http://youtube.com/results?" + urllib.parse.urlencode({"search_query": " ".join(args)})
    player = await vc.create_ytdl_player(url, ytdl_options=ytdl_opts)
    players[message.server] = player
    player.start()
    await reply(message, "Now playing in {}: {} (uploaded by {})".format(vc.channel.name, player.title, player.uploader))

@cmd
async def np(message, *args):
    "Now Playing"
    if not client.is_voice_connected(message.server):
        await reply(message, "Use !voice to join a voice channel")
        return
    vc = client.voice_client_in(message.server)
    if message.server not in players:
        await reply(message, "Nothing playing at the moment. Try !yt")
        return
    player = players[message.server]
    await reply(message, "Now playing in {}: {} (uploaded by {})".format(vc.channel.name, player.title, player.uploader))

@cmd
async def stop(message, *args):
    "Stops the current voice player"
    if message.server in players:
        players[message.server].stop()
        await reply(message, "Stopping.")
    else:
        await reply(message, "Nothing playing.")

@cmd
async def clearsince(message, *args):
    "Removes messages in bulk"
    if not await is_privileged(message.author):
        await reply(message, "You can't perform this action")
        return
    if not args or not all([i.isdigit() for i in args]):
        await reply(message, "Requires arguments, check datetime.datetime's constructor docs for usage <https://docs.python.org/3/library/datetime.html#datetime.datetime>")
        return
    x = 0
    deleted_messages = []
    async for log in client.logs_from(message.channel, after=datetime(*[int(i) for i in args])):
        deleted_messages.append("<{}> {}".format(log.author.name, log.content))
        await client.delete_message(log)
        x += 1
    await reply(message, "Deleted {} messages (by order of {})".format(x, message.author.name), rm=2)
    try:
        resp2 = await client.send_file(message.channel, StringIO("\n".join(deleted_messages)), filename="deleted-messages_{}.txt".format(int(datetime.now().timestamp())))
    except aiohttp.errors.ClientRequestError:
        with open("deleted-messages_{}.txt".format(int(datetime.now().timestamp())), "w") as f:
            f.write("\n".join(deleted_messages))
        await reply(message.channel, "Unable to send file to channel. Saved to bot directory", rm=2)

@client.event
async def on_message(message):
    txt = message.content
    for user in message.mentions:
        txt = txt.replace("<@{}>".format(user.id), "<@{}>".format(user.name))
    print("<{}> {}".format(message.author.name, txt), file=LOG)
    if client.user.id == message.author.id:
        return
    if client.user in message.mentions:
        cmd, *args = message.content.replace("<@{}>".format(client.user.id), "").split()
    elif message.content.startswith("!"):
        cmd, *args = message.content[1:].split()
    else:
        return
    if cmd in commands:
        await commands[cmd](message, *args)

@client.event
async def on_ready():
    print('Logged in as {} ({})'.format(client.user.name, client.user.id))

with open(".bottoken") as f:
    creds = f.read()
    if " " in creds:
        client.run(*creds.split(None, 1))
    else:
        client.run(creds.strip())
