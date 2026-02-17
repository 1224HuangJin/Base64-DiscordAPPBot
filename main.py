import discord
from discord.ext import commands
import base64
import os
from aiohttp import web
import asyncio

# --- 1. 交互界面：解码按钮 ---
class Base64View(discord.ui.View):
    def __init__(self):
        # timeout=None 是持久化视图的核心，保证机器人重启后按钮不失效 [1, 2]
        super().__init__(timeout=None)

    # custom_id 必须固定且唯一，用于在重启后重新匹配逻辑 [3]
    @discord.ui.button(label="查看原文 (仅自己可见)", style=discord.ButtonStyle.success, custom_id="base64_bot:decode_btn")
    async def decode_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # 从按钮所在的消息中提取 Base64 文本 [4]
            encoded_str = interaction.message.content
            decoded_bytes = base64.b64decode(encoded_str.encode('utf-8'))
            decoded_text = decoded_bytes.decode('utf-8')
            
            # 使用 ephemeral=True 发送只有点击者能看到的私密消息 [4, 5]
            await interaction.response.send_message(
                content=f"🔓 **解码成功！原文为：**\n{decoded_text}", 
                ephemeral=True
            )
        except Exception:
            await interaction.response.send_message(
                content="❌ 解码失败：该消息可能已被篡改或格式有误。", 
                ephemeral=True
            )

# --- 2. 防休眠：健康检查服务器 ---
# Koyeb 等平台需要检测程序是否占用端口，否则会判定为运行失败
async def health_check(request):
    return web.Response(text="Bot is alive!")

async def start_health_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    # Koyeb 默认检测 8080 端口
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()

# --- 3. 机器人主体 ---
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True # 必须在开发者后台开启此开关
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # 启动时注册持久化视图 [3, 6]
        self.add_view(Base64View())
        # 启动健康检查 Web 服务器
        asyncio.create_task(start_health_server())

    async def on_ready(self):
        print(f'已上线：{self.user}')

    async def on_message(self, message):
        # 预防死循环：忽略所有机器人发出的消息 [7, 8]
        if message.author.bot or not message.content:
            return

        # 1. 执行 Base64 编码 [9, 10]
        raw_content = message.content
        encoded_content = base64.b64encode(raw_content.encode('utf-8')).decode('utf-8')

        # 2. 检查长度上限（Base64 会使文本变长约 33%）
        if len(encoded_content) > 2000:
            return # 超过 Discord 单条消息 2000 字符限制则不处理

        # 3. 删除用户原消息（需要“管理消息”权限）[11, 12]
        try:
            await message.delete()
        except discord.Forbidden:
            print(f"无法删除 {message.author} 的消息，请检查权限。")
            return

        # 4. 发送转换后的消息和按钮
        await message.channel.send(content=encoded_content, view=Base64View())

# --- 4. 运行入口 ---
if __name__ == "__main__":
    bot = MyBot()
    # 生产环境建议通过环境变量读取 Token，更安全
    token = os.getenv('DISCORD_TOKEN')
    if token:
        bot.run(token)
    else:
        print("错误：未找到环境变量 DISCORD_TOKEN")
