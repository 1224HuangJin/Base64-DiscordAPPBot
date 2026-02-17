import discord
from discord.ext import commands
import base64
import os
from aiohttp import web
import asyncio

# --- 1. 交互界面：持久化解码按钮 ---
class Base64View(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # 永不过期 

    @discord.ui.button(label="查看原文 (私密显示)", style=discord.ButtonStyle.success, custom_id="persistent:decode_msg")
    async def decode_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # 只有点击的人能看到结果 (ephemeral=True) 
            encoded_str = interaction.message.content
            decoded_text = base64.b64decode(encoded_str.encode('utf-8')).decode('utf-8')
            await interaction.response.send_message(f"🔓 **私密解码结果：**\n{decoded_text}", ephemeral=True)
        except Exception:
            await interaction.response.send_message("❌ 解码失败，内容可能已被破坏。", ephemeral=True)

# --- 2. 防休眠：Koyeb 健康检查服务 ---
async def start_health_server():
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="Bot is running!"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()

# --- 3. 机器人主体逻辑 ---
class SuperBase64Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True  # 必须开启特权意图 
        super().__init__(command_prefix="!", intents=intents, help_command=None)
        # 用内存存储开启了自动转换的频道ID，重启后默认所有频道开启
        self.active_channels = set() 

    async def setup_hook(self):
        self.add_view(Base64View()) # 注册持久化视图 
        asyncio.create_task(start_health_server()) # 启动 Web 服务 [1]

    async def on_ready(self):
        print(f'已登录: {self.user} | 运行于 Koyeb')
        # 默认将机器人所在的频道都加入自动转换列表
        for guild in self.guilds:
            for channel in guild.text_channels:
                self.active_channels.add(channel.id)

    # 核心：处理自动转换逻辑
    async def on_message(self, message):
        if message.author.bot: return

        # 如果是指令（以! 开头），交给指令系统处理，不进行 Base64 转换
        if message.content.startswith(self.command_prefix):
            await self.process_commands(message)
            return

        # 检查当前频道是否开启了自动转换
        if message.channel.id in self.active_channels and message.content:
            raw_text = message.content
            encoded_text = base64.b64encode(raw_text.encode('utf-8')).decode('utf-8')

            if len(encoded_text) <= 2000:
                try:
                    await message.delete() # 删除原消息 [1]
                    await message.channel.send(content=encoded_text, view=Base64View())
                except discord.Forbidden:
                    print("权限不足，无法删除消息。")
            else:
                # 消息太长时发个私密提醒
                await message.channel.send(f"⚠️ {message.author.mention} 消息过长，无法转换。", delete_after=3)

# --- 4. 指令系统 ---
bot = SuperBase64Bot()

@bot.command()
async def ping(ctx):
    """查看延迟"""
    await ctx.send(f'🏓 延迟: {round(bot.latency * 1000)}ms')

@bot.command()
@commands.has_permissions(manage_channels=True)
async def toggle(ctx):
    """开启或关闭本频道的自动转换"""
    if ctx.channel.id in bot.active_channels:
        bot.active_channels.remove(ctx.channel.id)
        await ctx.send("🚫 本频道已**停用**自动 Base64 转换。")
    else:
        bot.active_channels.add(ctx.channel.id)
        await ctx.send("✅ 本频道已**启用**自动 Base64 转换。")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def clean(ctx, amount: int = 5):
    """清理频道消息 """
    await ctx.channel.purge(limit=amount + 1)
    await ctx.send(f"🧹 已清理 {amount} 条消息", delete_after=3)

@bot.command()
async def help_me(ctx):
    """显示帮助信息"""
    embed = discord.Embed(title="Base64 机器人指令菜单", color=0x00ff00)
    embed.add_field(name="!toggle", value="开启/关闭当前频道的自动转换功能", inline=False)
    embed.add_field(name="!clean [数量]", value="快速清理消息（需管理权限）", inline=False)
    embed.add_field(name="!ping", value="检查机器人在线状态", inline=False)
    embed.set_footer(text="直接发送文字即可自动转换为 Base64")
    await ctx.send(embed=embed)

# --- 5. 启动 ---
if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if token:
        bot.run(token)
    else:
        print("错误：请在 Koyeb 设置环境变量 DISCORD_TOKEN")
