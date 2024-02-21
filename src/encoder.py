import json
import re
from collections.abc import MutableMapping
from pandas.core.common import flatten
import numpy as np


class Encoder:
    """
    Used to prepare game state data for network forward-feeding.
    """
    # rounding error
    ERR_DIGITS = 16

    # numerical features
    STAT_MAX = 255
    BOOST_MAX = 12
    HP_MAX = 315
    PP_MAX = 40

    # categorical features (number of values, number of bits needed)
    ABILITIES = (123, 7)
    MOVES = (467, 9)
    POKEMON = (493, 9)
    ITEMS = (327, 9)
    GAME_STATE = (3, 2)

    # regex patterns
    ABILITY_PTN = re.compile(r'\w*Party\.\d\.Ability')
    ACTIVE_PTN = re.compile(r'\w*Party\.\d\.Active')
    ITEM_PTN = re.compile(r'\w*Party\.\d\.HeldItem')
    ID_PTN = re.compile(r'\w*Party\.\d\.ID')
    MOVE_ID_PTN = re.compile(r'\w*Party\.\d\.Moves\.\d\.ID')
    MOVE_PP_PTN = re.compile(r'\w*Party\.\d\.Moves\.\d\.PP')
    STATS_PTN = re.compile(r'\w*Party\.\d\.Stats\.[ATK|DEF|EVA|SPA|SPD]')
    BOOST_PTN = re.compile(r'\w*Party\.\d\.Stats\.\w*_Boost')
    STATUS_PTN = re.compile(r'\w*Party\.\d\.Stats\.Status')
    CONFUSED_PTN = re.compile(r'\w*Party\.\d\.Stats\.Confused')
    HP_PTN = re.compile(r'\w*Party\.\d\.Stats\.HP')
    STATE_PTN = "State"

    @classmethod
    def vectorize_state(cls, state: dict):
        """
        Encodes and vectorizes the given game input state.
        """
        state = cls.flatten_dict(state)
        encoded = []
        for k, v in state.items():
            if cls.ACTIVE_PTN.match(k):
                encoded += [v]
            # elif cls.ITEM_PTN.match(k):
            #     encoded += cls.encode_binary(v, cls.ITEMS[1])
            # elif cls.ABILITY_PTN.match(k):
            #     encoded += cls.encode_binary(v, cls.ABILITIES[1])
            elif cls.ID_PTN.match(k):
                encoded += cls.encode_binary(v, cls.POKEMON[1])
            # elif cls.MOVE_ID_PTN.match(k):
            #     encoded += cls.encode_binary(v, cls.MOVES[1])
            elif cls.MOVE_PP_PTN.match(k):
                encoded += [1 if v > 0 else 0]
            elif cls.BOOST_PTN.match(k):
                encoded += [round(v / cls.BOOST_MAX, cls.ERR_DIGITS)]
            elif cls.STATS_PTN.match(k):
                encoded += [round(v / cls.STAT_MAX, cls.ERR_DIGITS)]
            elif cls.STATUS_PTN.match(k) or cls.CONFUSED_PTN.match(k):
                encoded += cls.encode_binary(v, 8)  # 1-byte
            elif cls.HP_PTN.match(k):
                encoded += [round(v / cls.HP_MAX, cls.ERR_DIGITS)]
            elif cls.STATE_PTN == k:
                encoded += cls.encode_binary(v, cls.GAME_STATE[1])

        # flatten encoded values and vectorize
        input_layer = np.array(list(flatten(encoded)))
        return input_layer

    @classmethod
    def encode_binary(cls, x: int, n: int):
        return [int(i) for i in format(x, 'b').zfill(n)]

    @classmethod
    def flatten_dict(cls, d: MutableMapping, parent_key: str = '', sep: str = '.') -> MutableMapping:
        items = []
        for k, v in d.items():
            new_key = parent_key + sep + k if parent_key else k
            if isinstance(v, MutableMapping):
                items.extend(cls.flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)


class EncodingMatchException(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)
