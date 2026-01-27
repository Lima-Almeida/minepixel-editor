"""
Arquivo de configuração centralizado para o Minepixel Editor.
"""

from pathlib import Path

# ==================== CAMINHOS ====================

# Raiz do projeto
PROJECT_ROOT = Path(__file__).parent

# Assets
ASSETS_DIR = PROJECT_ROOT / "assets"
MINECRAFT_TEXTURES_DIR = ASSETS_DIR / "minecraft_textures"
BLOCKS_TEXTURE_DIR = MINECRAFT_TEXTURES_DIR / "blocks"
ICONS_DIR = ASSETS_DIR / "icons"

# Data
DATA_DIR = PROJECT_ROOT / "data"
BLOCKS_JSON = DATA_DIR / "blocks.json"

# Output (opcional - para salvar resultados)
OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


# ==================== CONFIGURAÇÕES DE RENDERIZAÇÃO ====================

# Tamanho padrão de cada bloco em pixels
DEFAULT_BLOCK_SIZE = 16

# Tamanho alvo padrão para conversão de imagens (em blocos)
# None = usa tamanho original da imagem
DEFAULT_TARGET_SIZE = None

# Qualidade de redimensionamento para previews
PREVIEW_MAX_SIZE = (800, 600)

# Cor da grade (RGBA) quando render_with_grid é usado
GRID_COLOR = (128, 128, 128, 128)


# ==================== CONFIGURAÇÕES DE MATCHING ====================

# Método de cálculo de distância de cores
# Opções: "delta_e", "euclidean"
COLOR_DISTANCE_METHOD = "delta_e"

# Threshold para considerar transparência
TRANSPARENCY_THRESHOLD = 0


# ==================== CONFIGURAÇÕES DA APLICAÇÃO ====================

# Título da janela
APP_TITLE = "Minepixel Editor"

# Tamanho inicial da janela
WINDOW_SIZE = (1280, 720)

# FPS máximo para a interface
MAX_FPS = 60


# ==================== CONFIGURAÇÕES DE DESENVOLVIMENTO ====================

# Modo debug
DEBUG = True

# Logging
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR

# Cache de texturas (manter em memória)
ENABLE_TEXTURE_CACHE = True


# ==================== FUNÇÕES AUXILIARES ====================

def ensure_directories():
    """Cria os diretórios necessários se não existirem."""
    ASSETS_DIR.mkdir(exist_ok=True)
    MINECRAFT_TEXTURES_DIR.mkdir(exist_ok=True)
    BLOCKS_TEXTURE_DIR.mkdir(exist_ok=True)
    ICONS_DIR.mkdir(exist_ok=True)
    DATA_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)


def validate_texture_pack():
    """
    Valida se o texture pack está configurado corretamente.
    
    Returns:
        tuple: (is_valid, message)
    """
    if not BLOCKS_TEXTURE_DIR.exists():
        return False, f"Pasta de texturas não encontrada: {BLOCKS_TEXTURE_DIR}"
    
    png_files = list(BLOCKS_TEXTURE_DIR.glob("*.png"))
    
    if len(png_files) == 0:
        return False, f"Nenhuma textura PNG encontrada em: {BLOCKS_TEXTURE_DIR}"
    
    return True, f"✓ {len(png_files)} texturas encontradas"


if __name__ == "__main__":
    # Teste de configuração
    print("=== Minepixel Editor - Configuração ===\n")
    
    print(f"📁 Raiz do projeto: {PROJECT_ROOT}")
    print(f"📁 Pasta de assets: {ASSETS_DIR}")
    print(f"📁 Texturas dos blocos: {BLOCKS_TEXTURE_DIR}")
    print(f"📁 Output: {OUTPUT_DIR}\n")
    
    print("🔧 Criando diretórios...")
    ensure_directories()
    print("   ✓ Diretórios criados\n")
    
    print("✅ Validando texture pack...")
    is_valid, message = validate_texture_pack()
    print(f"   {message}\n")
    
    if not is_valid:
        print("⚠️  ATENÇÃO: Configure as texturas do Minecraft!")
        print(f"   Consulte ASSETS_SETUP.md para instruções.\n")
    else:
        print("✨ Configuração OK! Pronto para usar.\n")
