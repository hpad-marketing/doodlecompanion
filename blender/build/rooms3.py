"""'More worlds' sets (approved 2026-10-30): spooky, adventure, show, everyday, backdrops.

Same entry format as rooms.py: (slug, label, model, x, y, rotZ, z=0, on=True, on_top_of=None).
Big pieces sit on the thirds, never straight behind Bunny's head.
"""
from rooms import W

ROOMS3 = {
    # ---------------------------------------------------------------- spooky
    'haunted': dict(name='Haunted room', kind='indoor', props=[
        ('chair', 'Sheet-covered chair', 'sheet_ghost_chair', -1.3, 1.4, 20),
        ('frames', 'Crooked portraits', 'hall_frames', 0.9, W - 0.04, 0, 0.1),
        ('candles', 'Candelabra', 'candelabra', 1.35, 1.2, 0, 0.0),
        ('web', 'Cobweb', 'cobweb', -2.15, W - 0.05, 0, 2.35),
        ('bulb', 'Flickering bulb', 'bare_bulb', 0.9, 0.6, 0, 2.4),
        ('window', 'Window', 'window', -1.3, W, 0, 0.9, False),
    ]),
    'foggyforest': dict(name='Foggy forest', kind='open', props=[
        ('tree-1', 'Dead tree', 'dead_tree', -1.6, 2.2, 15),
        ('tree-2', 'Dead tree 2', 'dead_tree', 1.9, 3.6, -30),
        ('tree-3', 'Far dead tree', 'dead_tree', -0.6, 7.0, 60),
        ('fog', 'Fog', 'fog_bank', 0.0, 2.8, 0),
        ('grave', 'Gravestone', 'gravestone', 1.2, 1.4, -12, 0.0, False),
        ('trees', 'Far treeline', 'far_treeline', 0.0, 40.0, 0),
    ]),
    'hallway': dict(name='Creaky hallway', kind='indoor', props=[
        ('door', 'Door left ajar', 'creaky_door', 1.4, W - 0.02, 0),
        ('frames', 'Portraits', 'hall_frames', -0.9, W - 0.04, 0, 0.1),
        ('rug', 'Runner rug', 'rug', 0.0, 0.8, 90),
        ('bulb', 'Bare bulb', 'bare_bulb', -0.8, 0.9, 0, 2.4),
        ('web', 'Cobweb', 'cobweb', 2.15, W - 0.05, 90, 2.35),
    ]),
    # ---------------------------------------------------------------- adventure
    'moonbase': dict(name='Moon base', kind='open', props=[
        ('dome', 'Dome', 'moon_dome', 2.2, 4.0, -20),
        ('crater', 'Crater', 'crater', -1.4, 2.6, 0),
        ('rocks', 'Moon rocks', 'moon_rocks', -0.4, 1.4, 0),
        ('flag', 'Flag', 'flag_pole', -1.7, 1.6, 10),
        ('earth', 'Earth in the sky', 'far_earth', -2.0, 30.0, 0, 5.0),
        ('stars', 'Stars', 'starfield', 0.0, 60.0, 0, -2.0),
    ]),
    'underwater': dict(name='Underwater', kind='open', props=[
        ('weed-1', 'Seaweed', 'seaweed', -1.5, 1.6, 0),
        ('weed-2', 'Seaweed 2', 'seaweed', 1.7, 2.4, 30),
        ('coral', 'Coral', 'coral', 1.1, 1.1, 0),
        ('fish', 'Fish school', 'fish_school', -1.2, 4.0, 0, 1.4),
        ('bubbles', 'Bubbles', 'bubbles_column', 0.7, 0.6, 0, 0.2),
        ('treasure', 'Sunken chest', 'treasure_sand', -1.8, 3.0, 20, 0.0, False),
    ]),
    'jungle': dict(name='Jungle', kind='open', props=[
        ('leaves-1', 'Big leaves', 'jungle_leaves', -1.7, 1.2, 20),
        ('leaves-2', 'Big leaves 2', 'jungle_leaves', 1.8, 1.8, -30),
        ('vines', 'Hanging vines', 'vines', 1.2, 2.6, 0, 2.6),
        ('tree', 'Palm', 'palm_tree', -1.2, 4.5, 0),
        ('fern', 'Fern', 'fern', 0.9, 0.9, 0),
        ('trees', 'Far treeline', 'far_treeline', 0.0, 40.0, 0),
    ]),
    'desert': dict(name='Desert', kind='open', props=[
        ('cactus-1', 'Cactus', 'cactus', 1.6, 2.2, 0),
        ('cactus-2', 'Small cactus', 'cactus', -2.2, 5.0, 40),
        ('dunes', 'Dunes', 'dunes', 0.0, 18.0, 0),
        ('rock', 'Rock', 'skull_rock', -1.2, 1.0, 0),
        ('sun', 'Sun', 'sun', 2.4, 40.0, 0, 5.0),
    ]),
    'snowpeak': dict(name='Snowy peak', kind='hills', props=[
        ('peak', 'Far peak', 'snow_peak', 1.2, 70.0, 0),
        ('drift', 'Snow drift', 'snow_drift', -1.4, 1.6, 0),
        ('pine-1', 'Snowy pine', 'pine_snow', 1.7, 2.0, 0),
        ('pine-2', 'Snowy pine 2', 'pine_snow', -2.0, 4.0, 0),
        ('flag', 'Summit flag', 'summit_flag', 0.9, 1.0, -20, 0.0, False),
    ]),
    'deepspace': dict(name='Space station', kind='indoor', props=[
        ('window', 'Space window', 'space_window', 0.0, W - 0.05, 0),
        ('consoles', 'Consoles', 'consoles', 1.4, 1.2, -30),
        ('chair', 'Captain chair', 'captain_chair', -1.2, 1.1, 30),
    ]),
    # ---------------------------------------------------------------- show sets
    'podcast': dict(name='Podcast desk', kind='indoor', props=[
        ('desk', 'Podcast desk', 'podcast_desk', 0.0, 0.55, 0),
        ('panels', 'Acoustic panels', 'acoustic_panels', 0.0, W - 0.04, 0),
        ('sign', 'On air sign', 'on_air_sign', 1.5, W - 0.04, 0, 1.95),
        ('plant', 'Plant', 'plant', -1.7, 1.6, 0),
        ('lamp', 'Floor lamp', 'floor_lamp', 1.75, 1.5, 0, 0, False),
    ]),
    'newsdesk': dict(name='News desk', kind='indoor', props=[
        ('desk', 'News desk', 'news_desk', 0.0, 0.5, 0),
        ('wall', 'News wall', 'news_wall', 0.0, W - 0.04, 0),
    ]),
    'concert': dict(name='Concert stage', kind='open', props=[
        ('stage', 'Stage', 'concert_stage', 0.0, 0.0, 0, 0.0),
        ('amp-l', 'Amps', 'amp_stack', -1.6, 1.6, 10),
        ('amp-r', 'Amps 2', 'amp_stack', 1.6, 1.6, -10),
        ('mic', 'Mic stand', 'mic_stand', 0.55, 0.3, 0),
        ('crowd', 'Crowd', 'crowd_heads', 0.0, -1.2, 0, -0.4, False),
    ]),
    'gameshow': dict(name='Game show', kind='indoor', props=[
        ('podium', 'Podium', 'game_podium', 0.0, 0.45, 0),
        ('wheel', 'Prize wheel', 'big_wheel', 1.5, 1.6, -15),
        ('lights', 'Stage lights', 'stage_lights', 0.0, 1.4, 0, 2.3),
        ('curtain', 'Curtain', 'fg_curtain', -2.0, 2.0, 0, 0.0),
    ]),
    'rapstudio': dict(name='Curved rap studio', kind='none', props=[
        ('cyc', 'Curved mustard backdrop', 'rap_cyc', 0.0, 0.0, 0),
        ('lights', 'Stage lights', 'stage_lights', 0.0, 0.8, 0, 2.6, False),
        ('mic', 'Mic stand', 'mic_stand', 0.6, 0.3, 0, 0.0, False),
    ]),
    # ---------------------------------------------------------------- everyday extras
    'carinside': dict(name='Inside a car', kind='none', props=[
        ('car', 'Car interior', 'car_interior', 0.0, 0.0, 0),
        ('road', 'Road outside', 'far_city', 0.0, 40.0, 0),
    ]),
    'businside': dict(name='Inside a bus', kind='cabin', props=[
        ('seats', 'Seats and poles', 'bus_interior', 0.0, 0.2, 0),
        ('window', 'Window view', 'train_window', -1.28, 1.0, 90, 0.9),
    ]),
    'lift': dict(name='Lift', kind='cabin', props=[
        ('walls', 'Buttons and rail', 'lift_walls', 0.0, 0.0, 0),
        ('door', 'Lift door', 'lift_door', 0.0, W - 0.03, 0),
    ]),
    'hospital': dict(name='Hospital room', kind='indoor', props=[
        ('bed', 'Hospital bed', 'hospital_bed', -1.3, 1.2, 90),
        ('iv', 'IV stand', 'iv_stand', -0.4, 1.7, 0),
        ('monitor', 'Heart monitor', 'heart_monitor', 1.5, 1.6, -20),
        ('window', 'Window', 'window', 1.0, W, 0, 0.9),
    ]),
    'library': dict(name='Library', kind='indoor', props=[
        ('stacks-l', 'Book stacks', 'library_stacks', -1.3, W - 0.2, 0),
        ('stacks-r', 'Book stacks 2', 'library_stacks', 1.6, W - 0.2, 0),
        ('table', 'Reading table', 'reading_table', 1.2, 0.9, -10),
        ('chair', 'Chair', 'dining_chair', 1.25, 0.35, 0, 0, False),
    ]),
    'cinema': dict(name='Cinema', kind='indoor', props=[
        ('screen', 'Big screen', 'cinema_screen', 0.0, W - 0.05, 0),
        ('seats', 'Seats', 'cinema_seats', 0.0, -1.0, 180),
        ('popcorn', 'Popcorn', 'popcorn_tub', 0.5, 0.3, 0, 0, False),
    ]),
    'rooftop': dict(name='Rooftop', kind='balcony', props=[
        ('parapet', 'Parapet', 'parapet', 0.0, 1.1, 0),
        ('tank', 'Water tank', 'rooftop_tank', -1.8, 0.4, 0),
        ('antenna', 'Antenna', 'antenna', 1.6, 0.8, 0),
        ('lights', 'String lights', 'string_lights_roof', 0.0, 0.5, 0, 0.0),
        ('city', 'City', 'far_city', 0.0, 40.0, 0, -12.0),
    ]),
    # ---------------------------------------------------------------- clean backdrops
    'cyc-mustard': dict(name='Mustard backdrop', kind='none', props=[
        ('cyc', 'Seamless sweep', 'cyc_sweep', 0.0, 0.8, 0),
    ]),
    'cyc-ink': dict(name='Ink backdrop', kind='none', props=[
        ('cyc', 'Seamless sweep', 'cyc_sweep', 0.0, 0.8, 0),
    ], ink=True),
    'corner': dict(name='Half-room corner', kind='corner', props=[]),
}
