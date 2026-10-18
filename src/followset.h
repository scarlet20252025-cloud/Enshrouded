// ============================================================================
//  WolfMount - the follow set
//
//  Just the bookkeeping: which entity ids are currently supposed to be trailing
//  the player. Kept separate from entityops.cpp so it can be unit tested without
//  linking anything that reads game memory -- the bugs in a set like this are
//  all bookkeeping bugs (leaking entries, dropping the wrong one, filling up
//  silently), and they are invisible in a log.
//
//  Why a follow set exists at all: this engine has no follow behaviour. See
//  entityops.h for the evidence.
// ============================================================================

#pragma once

#include <cstdint>

namespace wolfmount::followset {

// Upper bound on simultaneous followers. Small on purpose: each one costs a
// position read and a write per tick, and there is no gameplay reason to lead a
// pack larger than this.
constexpr int kMaxFollowers = 16;

// Add an entity. Returns true when it is now in the set (including when it
// already was). Returns false for id 0 or when the set is full.
bool Add(uint32_t entityId);

// Remove an entity. A no-op when it is not in the set.
void Remove(uint32_t entityId);

// Empty the set.
void Clear();

// How many entity ids the set holds.
int Count();

// The id at `index`, or 0 when out of range.
uint32_t At(int index);

// True when `entityId` is in the set.
bool Contains(uint32_t entityId);

} // namespace wolfmount::followset
