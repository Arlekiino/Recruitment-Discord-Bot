import discord
from discord.ext import commands
import os
import json
from dotenv import load_dotenv
import asyncio
from datetime import datetime, timedelta


load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')


RECRUIT_CHANNEL_ID = 123456789
STAFF_CHANNEL_ID =  123456789
MEMBER_ROLE_ID =    123456789
AUTO_ROLE_ID =      123456789
BLACKLIST_CHANNEL_ID = 123456789
LOG_CHANNEL_ID = 123456789
GRINCH_GREEN = discord.Color.from_rgb(72, 242, 5) 
BLACKLIST_FILE = "blacklist.json"


QUESTIONS = [
    "What is your BDO Family Name?",
    "How did you hear about us?",
    "Why do you want to join 'The Grinch'?",
    "Send a garmoth link of your gear"
]

pending_applications = set()  
rejection_cooldowns = {}      


def load_blacklist():
    if os.path.exists(BLACKLIST_FILE):
        with open(BLACKLIST_FILE, "r") as f:
            return json.load(f)
    return {"names": [], "message_id": None}

def save_blacklist(data):
    with open(BLACKLIST_FILE, "w") as f:
        json.dump(data, f, indent=4)

blacklist_data = load_blacklist()

async def update_blacklist_hud(guild):
    channel = guild.get_channel(BLACKLIST_CHANNEL_ID)
    if not channel: return
    names = blacklist_data["names"]
    embed = discord.Embed(title="🚫 THE GRINCH BLACKLIST 🚫", color=discord.Color.red())
    embed.description = "\n".join([f"• **{name}**" for name in names]) if names else "*The blacklist is currently empty.*"
    embed.set_footer(text=f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    if blacklist_data["message_id"]:
        try:
            msg = await channel.fetch_message(blacklist_data["message_id"])
            await msg.edit(embed=embed)
        except:
            msg = await channel.send(embed=embed)
            blacklist_data["message_id"] = msg.id
            save_blacklist(blacklist_data)
    else:
        msg = await channel.send(embed=embed)
        blacklist_data["message_id"] = msg.id
        save_blacklist(blacklist_data)


class DenyModal(discord.ui.Modal, title='Application Rejection Reason'):
    reason = discord.ui.TextInput(
        label='Reason for Rejection',
        style=discord.TextStyle.paragraph,
        placeholder='Explain why they were not a fit...',
        required=True,
        max_length=500,
    )

    def __init__(self, applicant_id: int):
        super().__init__()
        self.applicant_id = applicant_id

    async def on_submit(self, interaction: discord.Interaction):
        rejection_cooldowns[self.applicant_id] = discord.utils.utcnow() + timedelta(minutes=60)
        if self.applicant_id in pending_applications:
            pending_applications.remove(self.applicant_id)
        
        member = interaction.guild.get_member(self.applicant_id)
        if member:
            try:
              
                embed = discord.Embed(title="Application Status: Denied", color=discord.Color.red())
                embed.description = f"Hello, your application to **The Grinch** has been reviewed.\n\n**Reason:** {self.reason.value}"
                await member.send(embed=embed)
            except discord.Forbidden:
                pass 

        await interaction.response.edit_message(content=f"❌ **Denied by {interaction.user.name}**\n**Reason:** {self.reason.value}", view=None)


class ReviewView(discord.ui.View):
    def __init__(self, applicant_id: int):
        super().__init__(timeout=None)
        self.applicant_id = applicant_id

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green, custom_id="approve_btn")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.applicant_id in pending_applications:
            pending_applications.remove(self.applicant_id)

        member = interaction.guild.get_member(self.applicant_id)
        role = interaction.guild.get_role(MEMBER_ROLE_ID)
        if member and role:
            await member.add_roles(role)
            
            await member.send("✅ **Congratulations!** Your application to 'The Grinch' has been **Approved**.")
            await interaction.response.edit_message(content=f"✅ **Approved by {interaction.user.name}**", view=None)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.red, custom_id="deny_btn")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DenyModal(self.applicant_id))


class ApplyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Apply", style=discord.ButtonStyle.green, custom_id="apply_main")
    async def apply(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user
        now = discord.utils.utcnow()

        if user.id in rejection_cooldowns:
            remaining = rejection_cooldowns[user.id] - now
            if remaining.total_seconds() > 0:
                mins = int(remaining.total_seconds() // 60)
                await interaction.response.send_message(f"❌ Your application was recently rejected. Please wait **{mins} minutes** before trying again.", ephemeral=True)
                return

        if user.id in pending_applications:
            await interaction.response.send_message("❌ You already have a pending application! Please wait for staff review.", ephemeral=True)
            return

        pending_applications.add(user.id)
        await interaction.response.send_message(f"Check your DMs, {user.display_name}!", ephemeral=True)

        try:
            answers = []
            welcome_embed = discord.Embed(title="🟢 THE GRINCH RECRUITMENT 🟢", description="The interview process has started. Please answer the following questions clearly.\n\n*Note: You have 1 minute per question.*", color=GRINCH_GREEN)
            await user.send(embed=welcome_embed)

            for i, q in enumerate(QUESTIONS):
                q_embed = discord.Embed(title=f"Question {i+1} of {len(QUESTIONS)}", description=f"**{q}**", color=GRINCH_GREEN)
                q_embed.set_footer(text="Type your answer below...")
                await user.send(embed=q_embed)
                
                def check(m): return m.author == user and isinstance(m.channel, discord.DMChannel)
                
                try:
                    msg = await bot.wait_for('message', check=check, timeout=60.0)
                    if i == 0 and any(b_name.lower() == msg.content.strip().lower() for b_name in blacklist_data["names"]):
                        pending_applications.remove(user.id)
                        denied_embed = discord.Embed(title="🚫 Application Terminated", description="You are currently blacklisted from applying to **The Grinch**.", color=discord.Color.red())
                        await user.send(embed=denied_embed)
                        return
                    answers.append(msg.content)
                except asyncio.TimeoutError:
                    if user.id in pending_applications: pending_applications.remove(user.id)
                    await user.send("⏰ **Took too long to respond!** Please try again in **10 minutes**.")
                    return

            success_embed = discord.Embed(title="✅ Application Submitted", description="Thank you! Your form is now being reviewed by 'The Grinch' staff.", color=GRINCH_GREEN)
            await user.send(embed=success_embed)

            staff_channel = bot.get_channel(STAFF_CHANNEL_ID)
            embed = discord.Embed(title="New Application Submitted", color=discord.Color.blue())
            embed.set_author(name=f"{user.name} ({user.id})", icon_url=user.display_avatar.url)
            summary = "".join([f"**Q:** {QUESTIONS[i]}\n**A:** {answers[i]}\n\n" for i in range(len(QUESTIONS))])
            embed.description = summary
            await staff_channel.send(embed=embed, view=ReviewView(user.id))

        except discord.Forbidden:
            if user.id in pending_applications: pending_applications.remove(user.id)
            await interaction.followup.send("❌ Please open your DMs!", ephemeral=True)


class Grinch(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True 
        intents.members = True          
        intents.moderation = True 
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(ApplyView())
       
        if not os.path.exists('./cogs'):
            os.makedirs('./cogs')
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    print(f'✅ Loaded extension: {filename}')
                except Exception as e:
                    print(f'❌ Failed to load {filename}: {e}')

bot = Grinch()


@bot.event
async def on_member_join(member):
  
    auto_role = member.guild.get_role(AUTO_ROLE_ID)
    if auto_role:
        try: await member.add_roles(auto_role)
        except: pass

   
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        embed = discord.Embed(title="📥 Member Joined", description=f"{member.mention} has joined.", color=discord.Color.green())
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d"))
        await log_channel.send(embed=embed)

@bot.event
async def on_member_remove(member):
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if not log_channel: return
    await asyncio.sleep(2)
    
    async for entry in member.guild.audit_logs(limit=1, action=discord.AuditLogAction.kick):
        if entry.target.id == member.id and (discord.utils.utcnow() - entry.created_at).total_seconds() < 10:
            embed = discord.Embed(title="👢 Member Kicked", description=f"{member.name} was kicked by {entry.user.mention}", color=discord.Color.orange())
            embed.add_field(name="Reason", value=entry.reason or "No reason provided")
            await log_channel.send(embed=embed)
            return
    embed = discord.Embed(title="📤 Member Left", description=f"**{member.name}** has left the server.", color=discord.Color.light_grey())
    await log_channel.send(embed=embed)

@bot.event
async def on_member_ban(guild, user):
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if not log_channel: return
    await asyncio.sleep(2)
    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.ban):
        if entry.target.id == user.id:
            embed = discord.Embed(title="🔨 Member Banned", description=f"{user.name} was banned by {entry.user.mention}", color=discord.Color.red())
            embed.add_field(name="Reason", value=entry.reason or "No reason provided")
            await log_channel.send(embed=embed)
            break

@bot.event
async def on_member_update(before, after):
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if not log_channel: return
    if before.roles != after.roles:
        added = [r.mention for r in after.roles if r not in before.roles]
        removed = [r.mention for r in before.roles if r not in after.roles]
        if added or removed:
            embed = discord.Embed(title="🎭 Role Updated", description=f"Roles updated for {after.mention}", color=discord.Color.blue())
            if added: embed.add_field(name="Added", value=", ".join(added))
            if removed: embed.add_field(name="Removed", value=", ".join(removed))
            await log_channel.send(embed=embed)
    if before.timed_out_until != after.timed_out_until:
        if after.timed_out_until:
            embed = discord.Embed(title="⏳ Member Timed Out", color=discord.Color.dark_grey())
            embed.description = f"{after.mention} is muted until <t:{int(after.timed_out_until.timestamp())}:F>"
            await log_channel.send(embed=embed)

@bot.event
async def on_ready(): 
    print(f"Logged in as {bot.user}")
    for guild in bot.guilds: await update_blacklist_hud(guild)

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_recruit(ctx):
    await ctx.message.delete()
    recruit_channel = bot.get_channel(RECRUIT_CHANNEL_ID)
    embed = discord.Embed(title="🟢 Guild Application: TheGrinch 🟢", description="Press **Apply** button below to begin the interview process.", color=GRINCH_GREEN)
    if recruit_channel: await recruit_channel.send(embed=embed, view=ApplyView())


@bot.command()
@commands.has_permissions(administrator=True)
async def add_blacklist(ctx, *, family_name: str):
    await ctx.message.delete()
    if family_name not in blacklist_data["names"]:
        blacklist_data["names"].append(family_name); save_blacklist(blacklist_data); await update_blacklist_hud(ctx.guild)
        await ctx.send(f"✅ **{family_name}** added.", delete_after=5)

@bot.command()
@commands.has_permissions(administrator=True)
async def remove_blacklist(ctx, *, family_name: str):
    await ctx.message.delete()
    if family_name in blacklist_data["names"]:
        blacklist_data["names"].remove(family_name); save_blacklist(blacklist_data); await update_blacklist_hud(ctx.guild)
        await ctx.send(f"✅ **{family_name}** removed.", delete_after=5)

bot.run(TOKEN)