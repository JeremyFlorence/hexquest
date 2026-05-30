import random
from noise import pnoise2

from .models import HexTile

TERRAIN_WATER = "water"
TERRAIN_PLAINS = "plains"
TERRAIN_FOREST = "forest"
TERRAIN_HILL = "hill"
TERRAIN_MOUNTAIN = "mountain"
TERRAIN_DESERT = "desert"


def generate_world(game, width, height, seed):
    random.seed(seed)

    scale = 18.0
    octaves = 4
    persistence = 0.5
    lacunarity = 2.0

    elevation_base = random.randint(0, 1000)
    moisture_base = random.randint(0, 1000)

    tiles = []

    for q in range(width):
        for r in range(height):
            elevation = pnoise2(
                q / scale,
                r / scale,
                octaves=octaves,
                persistence=persistence,
                lacunarity=lacunarity,
                repeatx=width,
                repeaty=height,
                base=elevation_base,
            )

            moisture = pnoise2(
                q / scale + 100,
                r / scale + 100,
                octaves=octaves,
                persistence=persistence,
                lacunarity=lacunarity,
                repeatx=width,
                repeaty=height,
                base=moisture_base,
            )

            if elevation < -0.15:
                terrain = TERRAIN_WATER
            elif elevation > 0.55:
                terrain = TERRAIN_MOUNTAIN
            elif elevation > 0.3:
                terrain = TERRAIN_HILL
            elif moisture < -0.25:
                terrain = TERRAIN_DESERT
            elif moisture > 0.25:
                terrain = TERRAIN_FOREST
            else:
                terrain = TERRAIN_PLAINS

            tiles.append(
                HexTile(
                    game=game,
                    q=q,
                    r=r,
                    terrain=terrain,
                )
            )

    HexTile.objects.bulk_create(tiles)

    # Assign starting positions for nations
    nations = game.nations.all()
    available_tiles = list(HexTile.objects.filter(game=game).exclude(terrain=TERRAIN_WATER))
    
    if not available_tiles:
        # Fallback if everything is water (unlikely with noise settings but good for safety)
        available_tiles = list(HexTile.objects.filter(game=game))

    random.shuffle(available_tiles)

    from .models import Unit
    
    for nation in nations:
        if available_tiles:
            start_tile = available_tiles.pop()
            start_tile.owner = nation
            start_tile.save()
            
            # Set starting resources
            nation.gold = game.starting_gold
            nation.food = game.starting_food
            nation.save()
            
            # Create starting settler units
            for _ in range(game.starting_settlers):
                Unit.objects.create(
                    game=game,
                    nation=nation,
                    q=start_tile.q,
                    r=start_tile.r,
                    unit_type="settler"
                )
