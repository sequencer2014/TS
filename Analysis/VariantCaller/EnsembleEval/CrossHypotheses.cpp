/* Copyright (C) 2013 Ion Torrent Systems, Inc. All Rights Reserved */

#include "CrossHypotheses.h"


// model as a t-distribution to slightly resist outliers
/*float TdistThree(float res, float sigma){
  float x=res/sigma;
  float xx = x*x;
  return( 6.0f*sqrt(3.0f)/(sigma*3.14159f*(3.0f+xx)*(3.0f+xx)) );
}*/

//  control degrees of freedom for tradeoff in outlier resistance/sensitivity
float TDistOddN(float res, float sigma, float skew, int half_n) {
  // skew t-dist one direction or the other
  float l_sigma;
  if (res>0.0f){
    l_sigma = sigma*skew;
  } else {
    l_sigma = sigma/skew;
  }
  
  float x = res/l_sigma;
  float xx = x*x;
  float v = 2*half_n-1; // 1,3,5,7,...
  float my_likelihood = 1.0f/(3.14159f*sqrt(v));
  float my_factor = 1.0f/(1.0f+xx/v);

  for (int i_prod=0; i_prod<half_n; i_prod++) {
    my_likelihood *= my_factor;
  }
  for (int i_prod=1; i_prod<half_n; i_prod++) {
    my_likelihood *= (v+1.0f-2.0f*i_prod)/(v-2.0f*i_prod);
  }
  my_likelihood /= l_sigma;
  // account for skew
  float skew_factor = 2.0f*skew/(skew*skew+1.0f);
  my_likelihood *= skew_factor;
  return(my_likelihood);
}

void CrossHypotheses::CleanAllocate(int num_hyp, int num_flow){
  // allocate my vectors here
  responsibility.assign(num_hyp, 0.0f);
  log_likelihood.assign(num_hyp, 0.0f);
  scaled_likelihood.assign(num_hyp, 0.0f);
  
  tmp_prob_f.assign(num_hyp, 0.0f);
  tmp_prob_d.assign(num_hyp, 0.0);
  
  predictions.resize(num_hyp);
  normalized.resize(num_hyp);
  residuals.resize(num_hyp);
  sigma_estimate.resize(num_hyp);
  basic_likelihoods.resize(num_hyp);
  
  for (int i_hyp=0; i_hyp<num_hyp; i_hyp++){
    predictions[i_hyp].assign(num_flow, 0.0f);
        normalized[i_hyp].assign(num_flow, 0.0f);
        residuals[i_hyp].assign(num_flow, 0.0f);
        sigma_estimate[i_hyp].assign(num_flow, 0.0f);
        basic_likelihoods[i_hyp].assign(num_flow, 0.0f);
  }
  delta.assign(num_flow, 0.0f);
}


void CrossHypotheses::FillInPrediction(ion::FlowOrder &flow_order, ExtendedReadInfo &my_read) {

  int verbose           = 0;
  int normalize         = 0;

  // Check validity of input arguments
  if (my_read.start_flow < 0 or my_read.start_flow >= flow_order.num_flows()) {
    cerr << "CrossHypotheses::FillInPrediction: Start flow needs to be be larger than zero and smaller than the number of flows." << endl;
    cerr << "Start flow: " << my_read.start_flow << " Number of flows: " << flow_order.num_flows();
    assert(my_read.start_flow >= 0 and my_read.start_flow < flow_order.num_flows());
  }
  if (my_read.phase_params.size() != 3) {
    cerr << "CrossHypotheses::FillInPrediction: There need to be 3 phase parameters!" << endl;
    assert(my_read.phase_params.size() != 3);
  }
  for (int i=0; i<3; i++) {
    if (my_read.phase_params[i] < 0 or my_read.phase_params[i] > 1) {
      cerr << "CrossHypotheses::FillInPrediction: Phase parameters should be positive and smaller than one!" << endl;
      assert(my_read.phase_params[i] >= 0 and my_read.phase_params[i] <= 1);
    }
  }

  // something bad happens in CalculateHypDistances if we give reads of varying length
  // therefore pad
  vector<float> extended_measurement(flow_order.num_flows(), 0); // handle clipping
  for (unsigned int i=0; i<my_read.measurementValue.size(); i++)
    extended_measurement[i] = my_read.measurementValue[i];

  // allocate everything here
  CleanAllocate(instance_of_read_by_state.size(), flow_order.num_flows());

  // @TODO: think carefully about what needs to happen here
  // Probably want to keep the full solved read object per hypothesis
  // probably want to recycle treephaser
  // want to use floworder by bam to account for possible different runs
  max_last_flow = CalculateHypPredictions(extended_measurement, my_read.phase_params, flow_order,instance_of_read_by_state,
                                          my_read.start_flow, predictions, normalized, normalize, verbose);

  if (my_read.alignment.AlignmentFlag>0)
    strand_key = 1;
  else
    strand_key = 0;


}

void CrossHypotheses::InitializeTestFlows(){
    ComputeDelta(); // depends on predicted
  //@TODO: make this live
  ExtendedComputeTestFlow(min_delta_for_flow,max_flows_to_test); // flows changing by more than 0.1, 10 flows allowed

}

void CrossHypotheses::InitializeDerivedQualities() {
  InitializeResponsibility(); // depends on hypotheses
  InitializeTmpVariables();
  
  // in theory don't need to compute any but test flows
  ComputeBasicResiduals(); // predicted and measured

  InitializeSigma(); // depends on predicted
  ComputeBasicLikelihoods(); // depends on residuals and sigma
  // compute log-likelihoods
  ComputeLogLikelihoods();  // depends on test flow(s)
}

void CrossHypotheses::InitializeResponsibility() {
//  responsibility.resize(predictions.size());
  for (unsigned int i_hyp=0; i_hyp<responsibility.size(); i_hyp++)
    responsibility[i_hyp] = 0.0f;
  responsibility[0] = 1.0f;  // everyone is an outlier until we trust you
}

void CrossHypotheses::InitializeTmpVariables(){
//  tmp_prob_d.resize(predictions.size());
//  tmp_prob_f.resize(predictions.size());
}

// responsibility depends on the relative global probability of the hypotheses and the likelihoods of the observations under each hypothesis
// divide the global probabilities into "typical" data points and outliers
// divide the variant probabilities into each hypothesis (summing to 1)
// treat the 2 hypothesis case to start with
void CrossHypotheses::UpdateResponsibility(float reference_prob, float typical_prob) {

//  vector<double> tmp_prob(3);
  tmp_prob_d[0] = (1-typical_prob)*scaled_likelihood[0];   // i'm an outlier
  tmp_prob_d[1] = typical_prob * reference_prob * scaled_likelihood[1];
  tmp_prob_d[2] = typical_prob * (1-reference_prob) * scaled_likelihood[2];
  double ll_denom = tmp_prob_d[0]+tmp_prob_d[1]+tmp_prob_d[2];
  if (ll_denom<=0.0f){
    cout << "BADVAL: " << reference_prob << " " << typical_prob << " " << scaled_likelihood[0] << " " << scaled_likelihood[1] << " " << scaled_likelihood[2] << " " << ll_scale << endl;
    cout << "BADSPLICE: " << instance_of_read_by_state[0] << "\t" << instance_of_read_by_state[1] << "\t" << instance_of_read_by_state[2] << endl;
  }
  responsibility[0] = tmp_prob_d[0]/ll_denom;
  responsibility[1] = tmp_prob_d[1]/ll_denom;
  responsibility[2] = tmp_prob_d[2]/ll_denom;
}

float CrossHypotheses::ComputePosteriorLikelihood(float reference_prob, float typical_prob) {
//  vector<float> tmp_prob(3);
  tmp_prob_f[0] = (1-typical_prob)*scaled_likelihood[0];   // i'm an outlier
  tmp_prob_f[1] = typical_prob * reference_prob * scaled_likelihood[1];
  tmp_prob_f[2] = typical_prob * (1-reference_prob) * scaled_likelihood[2];
  float ll_denom = tmp_prob_f[0]+tmp_prob_f[1]+tmp_prob_f[2];
  if (ll_denom<=0.0f){
    cout << "BADVAL: " << reference_prob << " " << typical_prob << " " << scaled_likelihood[0] << " " << scaled_likelihood[1] << " " << scaled_likelihood[2]  << " " << ll_scale << endl;
    cout << "BADSPLICE: " << instance_of_read_by_state[0] << "\t" << instance_of_read_by_state[1] << "\t" << instance_of_read_by_state[2] << endl;
  }
  return(log(ll_denom)+ll_scale);  // log-likelihood under current distribution, including common value of log-likelihood-scale
}

void CrossHypotheses::ComputeDelta() {

//  delta.resize(predictions[0].size());
// difference between variants of interest, used for bias terms
  for (unsigned int j_flow=0; j_flow<delta.size(); j_flow++) {
    delta[j_flow] = predictions[2][j_flow]-predictions[1][j_flow];
  }
}

// really everything here should be across a window of "test flows" only
// making it over the full window to start "make correct, then make fast"
void CrossHypotheses::ComputeBasicResiduals() {
  // basic residuals are obviously predicted - normalized under each hypothesis
//  residuals.resize(predictions.size());
  for (unsigned int i_hyp=0; i_hyp<predictions.size(); i_hyp++) {
//    residuals[i_hyp].resize(predictions[i_hyp].size());
    for (unsigned int j_flow = 0; j_flow<predictions[i_hyp].size(); j_flow++) {
      residuals[i_hyp][j_flow] = predictions[i_hyp][j_flow]-normalized[i_hyp][j_flow];
    }
  }
}

void CrossHypotheses::ResetRelevantResiduals() {
  // basic residuals are obviously predicted - normalized under each hypothesis
  for (unsigned int i_hyp=0; i_hyp<predictions.size(); i_hyp++) {
    for (unsigned int t_flow=0; t_flow<test_flow.size(); t_flow++) {
      int j_flow = test_flow[t_flow];
      residuals[i_hyp][j_flow] = predictions[i_hyp][j_flow]-normalized[i_hyp][j_flow];
    }
  }
}

void CrossHypotheses::ComputeBasicLikelihoods() {

//  basic_likelihoods.resize(residuals.size());
  for (unsigned int i_hyp=0; i_hyp<basic_likelihoods.size(); i_hyp++) {
//    basic_likelihoods[i_hyp].resize(residuals[i_hyp].size());
    for (unsigned int j_flow = 0; j_flow<basic_likelihoods[i_hyp].size(); j_flow++) {
      basic_likelihoods[i_hyp][j_flow] = TDistOddN(residuals[i_hyp][j_flow],sigma_estimate[i_hyp][j_flow],skew_estimate, heavy_tailed);  // pure observational likelihood depends on residual + current estimated sigma under each hypothesis
    }
  }
}

void CrossHypotheses::UpdateRelevantLikelihoods() {
  for (unsigned int i_hyp=0; i_hyp<basic_likelihoods.size(); i_hyp++) {
    for (unsigned int t_flow=0; t_flow<test_flow.size(); t_flow++) {
      int j_flow = test_flow[t_flow];
      basic_likelihoods[i_hyp][j_flow] = TDistOddN(residuals[i_hyp][j_flow],sigma_estimate[i_hyp][j_flow],skew_estimate,heavy_tailed);  // pure observational likelihood depends on residual + current estimated sigma under each hypothesis
    }
  }
  ComputeLogLikelihoods(); // automatically over relevant likelihoods
}

void CrossHypotheses::ComputeLogLikelihoods() {
  //cout << "ComputeLogLikelihoods" << endl;
//  log_likelihood.resize(basic_likelihoods.size()); // number of hypotheses
  for (unsigned int i_hyp=0; i_hyp<log_likelihood.size(); i_hyp++) {
    log_likelihood[i_hyp] = 0.0f;
    for (unsigned int t_flow=0; t_flow<test_flow.size(); t_flow++) {
      int j_flow = test_flow[t_flow];
      log_likelihood[i_hyp] += log(basic_likelihoods[i_hyp][j_flow]);  // keep from underflowing from multiplying
    }
  }
  ComputeScaledLikelihood();
}

void CrossHypotheses::ComputeScaledLikelihood() {
  //cout << "ComputeScaledLikelihood" << endl;
//  scaled_likelihood.resize(log_likelihood.size());
  // doesn't matter who I scale to, as long as we scale together
  ll_scale = log_likelihood[0];
  for (unsigned int i_hyp =0; i_hyp<scaled_likelihood.size(); i_hyp++)
    if (log_likelihood[i_hyp]>ll_scale)
      ll_scale = log_likelihood[i_hyp];
  
  for (unsigned int i_hyp =0; i_hyp<scaled_likelihood.size(); i_hyp++)
    scaled_likelihood[i_hyp] = exp(log_likelihood[i_hyp]-ll_scale);
  // really shouldn't happen, but sometimes does if splicing has gone awry
  // prevent log(0) events from happening in case we evaluate under weird circumstances
  scaled_likelihood[0] = max(scaled_likelihood[0], MINIMUM_RELATIVE_OUTLIER_PROBABILITY);
}

// this needs to run past sigma_generator
void CrossHypotheses::InitializeSigma() {
  // guess the standard deviation given the prediction
  // as a reasonable starting point for iteration
  // magic numbers from some typical experiments
  // size out to match predictions
//  sigma_estimate.resize(predictions.size());
  for (unsigned int i_hyp=0; i_hyp<predictions.size(); i_hyp++) {
//    sigma_estimate[i_hyp].resize(predictions[i_hyp].size());
    for (unsigned int j_flow = 0; j_flow<predictions[i_hyp].size(); j_flow++) {
      float square_level = predictions[i_hyp][j_flow]*predictions[i_hyp][j_flow]+1.0f;
      sigma_estimate[i_hyp][j_flow] = magic_sigma_slope*square_level+magic_sigma_base;
    }
  }
}

// testing only
void CrossHypotheses::ComputeTestFlow() {
  test_flow.resize(1);
  float best = 0.0f;
  for (unsigned int j=0; j<delta.size(); j++) {
    if (fabs(delta[j])>best) {
      test_flow[0] = j;
      best = fabs(delta[j]);
    }
  }

}

// testing only
void CrossHypotheses::ExtendedComputeTestFlow(float threshold, int max_choice) {
  test_flow.resize(0);
  float best = 0.0f;
  int bestlocus = 0;
  for (unsigned int j=0; (j<delta.size()) & ((int)test_flow.size()<max_choice) & (j<(unsigned int)max_last_flow); j++) {
    if (fabs(delta[j])>best) {
      best = fabs(delta[j]);
      bestlocus = j;
    }
    if (fabs(delta[j])>threshold) {
      test_flow.push_back(j);
    }
  }
  if (test_flow.size()<1) {
    test_flow.push_back(bestlocus); // always at least one difference if nothing made threshold
    success=false; // but don't want it?
  }
}

// basic quality metric for this read
void CrossHypotheses::ComputeLocalDiscriminationStrength(float threshold, float &max_fld, int &reinforcing_flows){
  reinforcing_flows = 0;
  max_fld = 0.0f;
  for (unsigned int t_flow=0; t_flow<test_flow.size(); t_flow++){
    int j_flow = test_flow[t_flow];
    float approximate_fld = fabs(delta[j_flow]);
    approximate_fld /= sqrt(sigma_estimate[1][j_flow]*sigma_estimate[1][j_flow]+sigma_estimate[2][j_flow]*sigma_estimate[2][j_flow]);
    if (approximate_fld>threshold){
      reinforcing_flows++;
    }
    if (approximate_fld>max_fld)
      max_fld = approximate_fld;
  }
}

float CrossHypotheses::ComputeLLDifference(){
  // difference in likelihoods between hypotheses
  return(fabs(log_likelihood[2]-log_likelihood[1]));
}
