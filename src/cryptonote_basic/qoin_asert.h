// Qoin: difficulty from block QOIN_ASERT_HEIGHT on (next_difficulty_asert in difficulty.cpp).
//
// Bitcoin Cash's ASERT (aserti3-2d, same fixed-point constants) in difficulty form, anchored
// at block QOIN_ASERT_ANCHOR_HEIGHT. Anchor difficulty = BCH block height when this was set
// (970432) / temperature in Bellevue, Ohio at 03:14 Eastern on 2026-09-27 (50.9 F) / 3 = 6355.
// Half-life: pi hours. Replaces Wownero's v3-v5 formulas, which need 60-145 earlier blocks
// and read past the start of the chain when Qoin's compressed fork schedule reaches them at
// block 10.
//
// Kept out of cryptonote_config.h so that changing it only rebuilds the two files using it.

#pragma once

#include <cstdint>
#include "cryptonote_basic/difficulty.h"

#define QOIN_ASERT_HEIGHT                          10
#define QOIN_ASERT_ANCHOR_HEIGHT                   9
#define QOIN_ASERT_ANCHOR_PARENT_TIMESTAMP         1790493366   // timestamp of block 8
#define QOIN_ASERT_BCH_HEIGHT                      970432
#define QOIN_ASERT_BELLEVUE_TEMP_F_X10             509          // 50.9 F
#define QOIN_ASERT_DIVISOR                         3
#define QOIN_PI_E11                                314159265358ull  // 3.14159265358 x 10^11

namespace cryptonote
{
  difficulty_type next_difficulty_asert(uint64_t tip_height, uint64_t tip_timestamp);
}
