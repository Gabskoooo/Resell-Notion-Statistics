import discord
from discord import app_commands, ui
from discord.ext import commands

# --- CONFIGURATION ---
TOKEN = "MTQ3MzMyMDQyNzE0MDAyNjUyMQ.GJZbib.cOopdBhBRoktehqIoGvGpbmrPcX-yRuHojlIUw"


class MasterEmbedModal(ui.Modal, title='Détails du texte de l\'Embed'):
    embed_title = ui.TextInput(label='Titre', placeholder='Titre accrocheur...', required=True)
    embed_desc = ui.TextInput(label='Description', style=discord.TextStyle.paragraph, placeholder='Ton message ici...',
                              required=True)
    embed_footer = ui.TextInput(label='Texte du Footer', placeholder='Bas de page...', required=False)

    def __init__(self, channel, color, image_file=None, thumb_file=None):
        super().__init__()
        self.channel = channel
        self.color = color
        self.image_file = image_file  # Stocke l'image téléversée
        self.thumb_file = thumb_file  # Stocke la miniature téléversée

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title=self.embed_title.value,
            description=self.embed_desc.value,
            color=self.color
        )

        # On utilise l'URL générée par Discord pour tes fichiers téléversés
        if self.image_file:
            embed.set_image(url=self.image_file.url)
        if self.thumb_file:
            embed.set_thumbnail(url=self.thumb_file.url)
        if self.embed_footer.value:
            embed.set_footer(text=self.embed_footer.value)

        target_channel = self.channel or interaction.channel
        await target_channel.send(embed=embed)
        await interaction.response.send_message(f"✅ Embed avec fichiers envoyé dans {target_channel.mention}",
                                                ephemeral=True)


class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.default())

    async def setup_hook(self):
        await self.tree.sync()

    async def on_ready(self):
        print(f"✅ Connecté : {self.user.name}")


bot = MyBot()


@bot.tree.command(name="embed_pro", description="Créer un embed avec des fichiers images")
@app_commands.describe(
    salon="Le salon cible",
    couleur="Couleur Hex (ex: #2B2D31)",
    image="Téléverser la grande image",
    miniature="Téléverser la miniature"
)
async def embed_pro(
        interaction: discord.Interaction,
        salon: discord.TextChannel = None,
        couleur: str = "#2B2D31",
        image: discord.Attachment = None,
        miniature: discord.Attachment = None
):
    # Conversion de la couleur
    try:
        color_int = int(couleur.replace('#', ''), 16)
    except:
        color_int = discord.Color.blue().value

    # On ouvre le Modal en lui passant les fichiers récupérés dans la commande
    await interaction.response.send_modal(MasterEmbedModal(salon, color_int, image, miniature))


bot.run(TOKEN)