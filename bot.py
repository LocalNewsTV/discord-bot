#!/usr/bin/bash/python
import json, pytz, discord, random, os
from dotenv import load_dotenv
from discord.ext import commands, tasks
from datetime import time, datetime, timedelta
load_dotenv()


TOKEN = os.getenv('TOKEN', None)

##########################################################################
#               Helpers
###########################################################################
def get_schedule():
  file = open(SCHEDULE_FILE, "r")
  response = json.load(file)
  file.close()
  return response

def update_schedule():
  file = open(SCHEDULE_FILE, "w")
  file.write(json.dumps(config, indent=2))
  file.close()

def log(ctx):
  log = open("log.txt", "a")
  log.write(f'[{datetime.now()}][{ctx.author.name}|{ctx.author.display_name}]: {ctx.message.content}\n')
  log.close()
##########################################################################
#               START
###########################################################################
SCHEDULE_FILE = 'config.json'
config = get_schedule()
ADMIN_WHITELIST = config['admins']
GRANTABLE_ROLES = config['grantable_roles']
ALERT_CHANNEL_IDS = config['alert_channel_ids']
print(ADMIN_WHITELIST, GRANTABLE_ROLES, ALERT_CHANNEL_IDS)
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.listen()
async def on_ready():
  guild_count = 0
  for guild in bot.guilds:
    print(f"- {guild.id} (name: {guild.name})")
    guild_count += 1
  scheduler.start()


##########################################################################
#               Success/Fail Handling
###########################################################################
async def on_action_success(ctx, msg=None):
  SUCCESS = '⭕'
  log(ctx)
  await ctx.message.add_reaction(SUCCESS)
  if(msg):
    await ctx.send(msg + ctx.author.mention)

async def on_action_failure(ctx, msg=None):
  FAIL = '❌'
  log(ctx)
  await ctx.message.add_reaction(FAIL)
  if(msg):
    await ctx.send(msg + ctx.author.mention)


##########################################################################
#               CALL HANDLING
###########################################################################
@bot.command()
async def join(ctx):
  if (ctx.author.voice):
    channel = ctx.author.voice.channel
    await channel.connect()
  else:
    await ctx.send("You must be in a voice channel first so I can join it.")

@bot.command()
async def leave(ctx):
  print(ctx)
  if (ctx.voice_client):
    await ctx.voice_client.disconnect()
  else:
    await ctx.send("I'm not in a voice channel, use the join command to make me join")


##########################################################################
#               ALERT HANDLING
###########################################################################
@tasks.loop(minutes=1)
async def scheduler():
  alerts = []
  for key in config['events']:
    if config['events'][key]['alertsOn']:
      if datetime.now().strftime("%H:%M") in config['events'][key]['schedule']:
        message = random.choice(config['events'][key]['messages'])
        role = config['events'][key]['roleID']
        alerts.append(f'{message} <@&{role}>')
  for channel_id in ALERT_CHANNEL_IDS:
    channel = bot.get_channel(channel_id)
    for alert in alerts:
      await channel.send(alert)

@bot.command(aliases=['alerts', 'active', 'pings'])
async def active_alert(ctx):
  response = []
  for key in config['events']:
      response.append(f"- **{config['events'][key]['title']}**: `{config['events'][key]['alertsOn']}`")
  if not response:
    await ctx.send("No events currently active")
  else:
    response.insert(0, "Currently sending alerts for these events:")
    await ctx.send("\n".join(response))
       
@bot.command()
async def turn_on_alert(ctx, item):
  print(ctx.author.name in ADMIN_WHITELIST)
  if (ctx.author.name in ADMIN_WHITELIST):
    item = item.lower()
    if config['events'].get(item, None):
      config['events'][item]['alertsOn'] = True
      update_schedule()
      return await on_action_success(ctx)
    else:
      return await on_action_failure(ctx, "Alert not found")
  await on_action_failure(ctx, "Unauthorized. For admin use only")

@bot.command()
async def turn_off_alert(ctx, item):
  if ctx.author.name in ADMIN_WHITELIST:
    item = item.lower()
    if config['events'].get(item, None):
      config['events'][item]['alertsOn'] = False
      update_schedule()
      await on_action_success(ctx)
      return
    else:
      return await on_action_failure(ctx, "Alert not found")
  await on_action_failure(ctx, "Unauthorized. For admin use only")


##########################################################################
#               Events running right now
###########################################################################
@bot.command(aliases=["now"])
async def whats_happening(ctx):
  """Display all active events occurring"""
  timezone = pytz.timezone("America/Vancouver")
  current_time = datetime.now(timezone).time()
  response = []
  
  for key in config['events']:
    event = config['events'][key]
    if event['alertsOn']:
      isActive = False
      for eventTime in event['schedule']:
        hours, minutes = map(int, eventTime.split(":"))
        start_time = time(hours, minutes)

        duration = event['duration']
        start_datetime = datetime.combine(datetime.today(), start_time)
        end_datetime = start_datetime + timedelta(minutes=duration)
        end_time = end_datetime.time()
        if start_time <= current_time <= end_time:
          isActive = True
          break
      if isActive:
        response.append(f"- {config['events'][key]['title']}")

  if not response:
      response.append("No events are currently active.")
  else:
    response.insert(0, "Currently Happening:")
  await ctx.send("\n".join(response))
  await on_action_success(ctx)


##########################################################################
#               ROLE HANDLING
###########################################################################
@bot.command()
async def grant_role(ctx, role: discord.Role):
  """Grants role to a user (case-sensitive) "!grant_role Colo"
  Usage: 
    -`!grant_role <Role> or <@Role>`
  Example:
    -`!grant_role Colo`
  """
  member = ctx.author
  if role in member.roles:
    await on_action_failure(ctx, f"You already have the `{role.name}` role ")
    return
  
  if role in GRANTABLE_ROLES or role.position < member.top_role.position:
    await member.add_roles(role, reason="Requested by user", atomic=True)
    await on_action_success(ctx, "Role Granted")
  else:
    await on_action_failure(ctx, f"Unable to grant you the role `{role.name}`.")
  
@grant_role.error
async def grant_role_error(ctx, error):
  text = None
  if isinstance(error, commands.RoleNotFound):
    text = "Role not found"
  await on_action_failure(ctx, text)

@bot.command()
async def drop_role(ctx, role: discord.Role):
  """Revoke role from user (case-sensitive) "!drop_role Colo"
  Usage: 
    -`!drop_role <Role> or <@Role>`
  Example
    -`!drop_role Colo`
  """
  member = ctx.author
  if role in member.roles:
    await member.remove_roles(role, reason="Requested by user", atomic=True)
    await on_action_success(ctx, "Role removed")
  else:
    await on_action_failure(ctx, f"You don't have the role `{role.name}`")


@drop_role.error
async def drop_role_error(ctx, error):
  text = None
  if isinstance(error, commands.RoleNotFound):
    text = "Role not found"
  await on_action_failure(ctx, text)



bot.run(TOKEN)
