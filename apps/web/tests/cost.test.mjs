import test from "node:test";
import assert from "node:assert/strict";
import {monthlyCost} from "../src/lib/cost.js";

const model={inputPrice:2,outputPrice:8,cacheReadPrice:0.5,currency:"USD"};
test("monthly cost uses input, output and cache read prices",()=>{
  const result=monthlyCost(model,{requestsPerDay:1000,inputTokens:1000,outputTokens:500,cacheHit:50});
  assert.equal(result.amount,157.5);
  assert.equal(result.currency,"USD");
});
test("missing prices do not turn into zero cost",()=>{
  assert.equal(monthlyCost({...model,outputPrice:null},{requestsPerDay:1000,inputTokens:1000,outputTokens:500,cacheHit:0}),null);
});
test("missing cache price falls back to full input price",()=>{
  const result=monthlyCost({...model,cacheReadPrice:null},{requestsPerDay:1000,inputTokens:1000,outputTokens:500,cacheHit:50});
  assert.equal(result.amount,180);
  assert.equal(result.cacheEstimated,true);
});
