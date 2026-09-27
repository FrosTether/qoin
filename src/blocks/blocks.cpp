#include "blocks.h"

#include <unordered_map>

extern const unsigned char checkpoints[];
extern const size_t checkpoints_len;

namespace blocks
{

  // Qoin: no precomputed block hashes. The embedded checkpoints.dat holds
  // Wownero's block hashes, which would conflict with this chain.
  const std::unordered_map<cryptonote::network_type, const epee::span<const unsigned char>, std::hash<size_t>> CheckpointsByNetwork = {
  };

  const epee::span<const unsigned char> GetCheckpointsData(cryptonote::network_type network)
  {
    const auto it = CheckpointsByNetwork.find(network);
    if (it != CheckpointsByNetwork.end())
    {
      return it->second;
    }
    return nullptr;
  }

}
