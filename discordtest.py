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

commands = {}
players = {}

async def cleanup(messages):
    await asyncio.sleep(30)
    for message in messages:
        await client.delete_message(message)

async def is_privileged(member):
    for role in member.server.roles:
        if role.name == "b3BotUser":
            if role in member.roles:
                return True
    return False

def cmd(func):
    commands[func.__name__] = func
    def dec(*args, **kwargs):
        return func(*args, **kwargs)
    return dec

@cmd
async def help(message, *args):
    "Returns this message"
    out = "\n".join(["!{}: {}".format(command, cmd_func.__doc__) for command, cmd_func in commands.items()])
    resp = await client.send_message(message.channel, "```{}```".format(out))
    await cleanup([message, resp])

@cmd
async def sleep(message, *args):
    "Naps for five seconds"
    resp = await client.send_message(message.channel, ":sleeping:")
    await asyncio.sleep(5)
    await client.edit_message(resp, 'Hi there!')
    await cleanup([message, resp])

@cmd
async def invite(message, *args):
    "Returns the link to invite b3Bot to your server"
    resp = await client.send_message(message.channel, discord.utils.oauth_url(client.user.id))
    await cleanup([message, resp])

@cmd
async def source(message, *args):
    "Returns the source for b3Bot"
    with open(__file__) as f:
        source = f.read()
    await client.send_typing(message.channel)
    with aiohttp.ClientSession() as session:
        data = aiohttp.FormData()
        data.add_field("c", StringIO(source), filename="b3bot.py")
        headers = {"Accept": "application/json"}
        async with session.post("https://ptpb.pw", data=data, headers=headers) as resp:
            d = await resp.json()
            response = await client.send_message(message.channel, d["url"] + "/py")
    await cleanup([message, response])

@cmd
async def react(message, *args):
    "Lets users react!"
    await cleanup([message])
    msg = await client.send_message(message.channel, 'React with thumbs up or thumbs down.' if not args else " ".join(args))
    while True:
        res = await client.wait_for_reaction(['👍', '👎', '❌'], message=msg)
        if res.reaction.emoji == '❌':
            await client.edit_message(msg, "Okay :<")
            await cleanup([res])
            break

@cmd
async def voice(message, *args):
    "Tells b3Bot to join a voice channel"
    if not await is_privileged(message.author):
        resp = await client.send_message(message.channel, "You can't perform this action")
        await cleanup([message, resp])
        return
    if not discord.opus.is_loaded():
        discord.opus.load_opus(ctypes.util.find_library("opus"))
    if not message.server:
        return
    channels = {channel.name: channel for channel in message.server.channels if channel.type is discord.ChannelType.voice}
    if not channels:
        resp = await client.send_message(message.channel, "No voice channels")
    else:
        if args:
            dest = channels[args[0]] if channels and args[0] in channels else None
            vc = client.voice_client_in(message.server)
            if vc:
                await vc.move_to(dest)
            else:
                await client.join_voice_channel(dest)
            resp = await client.send_message(message.channel, "Joined " + dest.name)
        else:
            resp = await client.send_message(message.channel, "Choose one of: " + ", ".join(channels.keys()))
    await cleanup([message, resp])

@cmd
async def vleave(message, *args):
    if not await is_privileged(message.author):
        resp = await client.send_message(message.channel, "You can't perform this action")
        await cleanup([message, resp])
        return
    await client.voice_client_in(message.server).disconnect()
    resp = client.send_message(message.channel, "Disconnected from voice channel")
    await cleanup([message, resp])

@cmd
async def yt(message, *args):
    "Starts playing a given youtube video or search result"
    if not client.is_voice_connected(message.server):
        resp = await client.send_message(message.channel, "Use !voice to join a voice channel")
        await cleanup([message, resp])
        return
    resp = None
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
    resp = await client.send_message(message.channel, "Now playing in {}: {} (uploaded by {})".format(vc.channel.name, player.title, player.uploader))
    if not resp:
        resp = await client.send_message(message.channel, "No voice client found! :o")
    await cleanup([message, resp])

@cmd
async def stop(message, *args):
    "Stops the current voice player"
    if message.server in players:
        players[message.server].stop()
        resp = await client.send_message(message.channel, "Stopping.")
        await cleanup([message, resp])
    else:
        resp = await client.send_message(message.channel, "Nothing playing.")
        await cleanup([message, resp])

unused_commands = """@cmd
async def clearlastday(message, *args):
    "Removes messages from the past day"
    if not await is_privileged(message.author):
        resp = await client.send_message(message.channel, "You can't perform this action")
        await cleanup([message, resp])
        return
    n = datetime.now()
    x = 0
    async for log in client.logs_from(message.channel, after=datetime(n.year, n.month, n.day)):
        await client.delete_message(log)
        x += 1
    resp = await client.send_message(message.channel, "Deleted {} messages (by order of {})".format(x, message.author.name))
"""

@client.event
async def on_message(message):
    print("<{}> {}".format(message.author.name, message.content), file=LOG)
    if client.user.id == message.author.id:
        return
    if message.content.startswith('!'):
        cmd, *args = message.content[1:].split()
        if cmd in commands:
            await commands[cmd](message, *args)

@client.event
async def on_ready():
    print('Logged in as {} ({})'.format(client.user.name, client.user.id))

with open(".bottoken") as f:
    client.run(f.read().strip())
