export const PROVIDER_NAMES = { openai:"OpenAI", anthropic:"Anthropic", google:"Google", meta:"Meta", deepseek:"DeepSeek", alibaba:"Alibaba", xai:"xAI", mistral:"Mistral", zhipu:"Zhipu" };
export const SCORE_LABELS = {
  artificial_analysis_intelligence_index:"AA Intelligence",
  artificial_analysis_coding_index:"AA Coding",
  artificial_analysis_agentic_index:"AA Agentic",
};
export const COMPARE_BENCHMARKS = Object.values(SCORE_LABELS);
export const PROVIDER_COLORS = { OpenAI:"#10a37f", Anthropic:"#d97757", Google:"#4285f4", Meta:"#0866ff", DeepSeek:"#3459dd", Alibaba:"#f26722", xAI:"#c9d4e5", Mistral:"#fa520f", Zhipu:"#1f6feb" };
export function providerColor(name) { return PROVIDER_COLORS[name] || "#8b94a7"; }

export function compactTokens(value) {
  if (!value) return "—";
  if (value >= 1_000_000) return `${Number((value / 1_000_000).toFixed(2))}M`;
  if (value >= 1_000) return `${Math.round(value / 1000)}K`;
  return String(value);
}

export function stampDate(value) { return value ? String(value).slice(0, 10) : null; }
export function stampDateTime(value) { return value ? String(value).slice(0, 16).replace("T", " ") : null; }

export function mapApiModel(item) {
  const evaluations=item.evaluations||[], scores={};
  evaluations.forEach(e=>{ if(SCORE_LABELS[e.benchmark_slug]) scores[SCORE_LABELS[e.benchmark_slug]]=Number(e.score); });
  const headline=evaluations.find(e=>e.benchmark_slug==="artificial_analysis_intelligence_index")||evaluations[0];
  const variant=item.variant||{};
  const capabilitySource=item.capability_source;
  const capabilities=capabilitySource?[
    variant.supports_text&&"文本", variant.supports_image&&"图片",
    variant.supports_audio&&"音频", variant.supports_video&&"视频",
    variant.supports_reasoning&&"推理", variant.supports_tool_calling&&"工具调用",
  ].filter(Boolean):[];
  const price=item.pricing||{}, performance=item.performance||{};
  return {
    id:item.slug, name:item.canonical_name, provider:item.provider_name||PROVIDER_NAMES[item.provider]||item.provider,
    release:item.release_date||"—", context:compactTokens(variant.context_window),
    contextTokens:variant.context_window||null, capabilities, capabilitySource,
    inputPrice:price.input_price_per_million==null?null:Number(price.input_price_per_million),
    outputPrice:price.output_price_per_million==null?null:Number(price.output_price_per_million),
    cacheReadPrice:price.cached_input_price==null?null:Number(price.cached_input_price),
    currency:price.currency||null, pricingProvider:price.provider_name||null,
    speed:performance.tokens_per_second==null?null:Number(performance.tokens_per_second),
    description:item.description||null,
    eval:headline?Number(headline.score):null, benchmark:headline?(SCORE_LABELS[headline.benchmark_slug]||headline.benchmark_name):"待评测",
    source:headline?.source||"Registry", variants:[variant.name||"standard"],
    endpoint:item.endpoint?.external_model_id||"暂无端点", score:scores,
    snapshotId:headline?.source_snapshot_id, observedAt:headline?.observed_at, live:true,
  };
}

export async function loadModelEvaluations(slug) {
  const response=await fetch(`/api/v1/models/${encodeURIComponent(slug)}/evaluations?limit=500`);
  if(!response.ok) throw new Error("Evaluation API unavailable");
  const body=await response.json();
  return body.items||[];
}

export function mapApiBenchmark(item) {
  const categoryMap={coding:"代码",reasoning:"推理",agent:"智能体",composite:"综合",multimodal:"多模态",knowledge:"知识"};
  const version=item.versions?.[0], metric=version?.metrics?.[0];
  const inferredCategory=item.slug?.includes("coding")?"代码":item.slug?.includes("agentic")?"智能体":"综合";
  return { id:item.slug, name:SCORE_LABELS[item.slug]||item.name, category:categoryMap[item.category]||inferredCategory, capability:item.capabilities?.map(x=>x.name).join(" / ")||inferredCategory,
    version:version?.version&&version.version!=="source"?version.version:"未记录", metric:metric?.name||"—", risk:item.contamination_risk==="low"?"低":item.contamination_risk==="high"?"高":item.contamination_risk==="medium"?"中":"未提供",
    results:item.result_count??"—", updated:"未提供", description:item.description||"暂无说明", method:`${metric?.name||"Score"} · ${metric?.score_direction||"higher_better"}` };
}

export async function loadModels() {
  const items=[];
  let cursor=null;
  do {
    const url=`/api/v1/models?status=preview&limit=100&include_summary=true${cursor?`&cursor=${encodeURIComponent(cursor)}`:""}`;
    const response=await fetch(url);
    if(!response.ok) throw new Error("Model API unavailable");
    const body=await response.json();
    items.push(...body.items);
    cursor=body.next_cursor;
  } while(cursor);
  const cutoff=new Date(Date.now()-90*24*60*60*1000).toISOString().slice(0,10);
  return items.filter(item=>item.release_date&&item.release_date>=cutoff)
    .sort((a,b)=>b.release_date.localeCompare(a.release_date))
    .map(mapApiModel);
}

export async function loadBenchmarks() {
  const benchmarkResponse=await fetch("/api/v1/benchmarks?limit=100");
  if(!benchmarkResponse.ok) throw new Error("Benchmark API unavailable");
  const benchmarkBody=await benchmarkResponse.json();
  const benchmarkDetails=await Promise.all(benchmarkBody.items.map(async item=>{
    const response=await fetch(`/api/v1/benchmarks/${item.slug}`);
    return response.ok?{...item,...await response.json()}:item;
  }));
  return benchmarkDetails.map(mapApiBenchmark);
}

export async function loadStatus() {
  const response=await fetch("/api/v1/status");
  if(!response.ok) throw new Error("Status API unavailable");
  return response.json();
}
