export function monthlyCost(model, {requestsPerDay, inputTokens, outputTokens, cacheHit}) {
  const {inputPrice, outputPrice, cacheReadPrice, currency} = model;
  if(!currency || !Number.isFinite(inputPrice) || !Number.isFinite(outputPrice)) return null;
  const hit=Math.min(100,Math.max(0,Number(cacheHit)||0))/100;
  const inputUnit=inputPrice*(1-hit)+(cacheReadPrice??inputPrice)*hit;
  const daily=(Math.max(0,Number(inputTokens)||0)*inputUnit+Math.max(0,Number(outputTokens)||0)*outputPrice)/1_000_000;
  return {amount:daily*Math.max(0,Number(requestsPerDay)||0)*30,currency,cacheEstimated:hit>0&&cacheReadPrice==null};
}
