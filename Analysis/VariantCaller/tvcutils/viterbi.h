/* Copyright (C) 2015 Ion Torrent Systems, Inc. All Rights Reserved */

/* Author: Alex Artyomenko <aartyomenko@cs.gsu.edu> */

#ifndef ION_ANALYSIS_VITERBI_H
#define ION_ANALYSIS_VITERBI_H

using namespace std;

#define MAX_STATE_VALUE 100000

struct markov_state {
  double value, prev, current;
  boost::math::poisson dist;

  markov_state() : value(0), prev(0), current(0), dist(0) { }
  markov_state(double value) : value(value), prev(0), current(0), dist(value) { }

  double cost(double v) {
    // cost of being in the state under Poisson distribution log pdf to make is additive
    double rounded_v = min(v, (double)MAX_STATE_VALUE);
    // increase cost of small values to report spikes down in gvcf
    //return rounded_v < 0.75 * dist.mean() ? -numeric_limits<double>::infinity() : log(boost::math::pdf(dist, rounded_v));
	//to prevent overflow use alternate math solution using Stirling's approximation.
    return rounded_v < 0.75 * dist.mean() ? -numeric_limits<double>::infinity() : rounded_v * log(value) - value - (rounded_v * log(rounded_v) - rounded_v + sqrt(log(2 * 3.14159265359 * rounded_v)));
  }

  double cost(const markov_state& st) { return st.value == value ? 0 : -5E2; }

  void step_forward() { prev = current; }
};

struct markov_chain_comparator {
  markov_state * current;
  markov_chain_comparator() : current(NULL) { }
  markov_chain_comparator(markov_state& current) : current(&current) { }
  bool operator()(const markov_state& lhs, const markov_state& rhs) {
    // special comparator functor to implement state selection in building markov chain
    if (current) {
      double lhs_cost = lhs.prev + current->cost(lhs),
          rhs_cost = rhs.prev + current->cost(rhs);
      return lhs_cost > rhs_cost;
    }
    return lhs.current > rhs.current;
  }
};

template<typename T>
struct depth_info {
  T dp, min_dp, max_dp;
  depth_info() : dp(0), min_dp(numeric_limits<T>::max()), max_dp(numeric_limits<T>::min()) { }
  depth_info(T dp, T min_dp, T max_dp) : dp(dp), min_dp(min_dp), max_dp(max_dp) { }
  depth_info(T dp) : dp(0), min_dp(dp), max_dp(dp) { }
};

template<typename T>
class markov_chain : vector< vector<long> > {
  vector<markov_state> states;
  vector<pair<depth_info<T>, long> > items;
  vector<T> values;
  markov_chain() { }
public:
  template<typename _ForwardIterator>
  markov_chain(_ForwardIterator begin, _ForwardIterator end);
  template<typename _ForwardIterator>
  markov_chain(_ForwardIterator begin, _ForwardIterator end, T min, T max);
  ~markov_chain() { };

  markov_state state(long i) { return states[i]; }

  typename vector<pair<depth_info<T>, long> >::reverse_iterator ibegin() { return items.rbegin(); }
  typename vector<pair<depth_info<T>, long> >::reverse_iterator iend()   { return items.rend(); }
private:
  void generate_states(T min, T max);
  void process_next_value(T val);
  void optimal_path();
  template<typename _ForwardIterator>
  void initialize(_ForwardIterator begin, _ForwardIterator end, T min, T max);
};

#include "viterbi.hpp"

#endif //ION_ANALYSIS_VITERBI_H
