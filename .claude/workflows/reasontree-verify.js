export const meta = {
  name: 'reasontree-verify',
  description: 'Bounded reasoning tree (tournament + adversarial refutation): tournament search, then independent skeptics attack the chosen path before the answer ships',
  whenToUse: 'High-stakes multi-step decisions where a plausible-but-wrong answer is costly and the winning path should survive adversarial review',
  phases: [
    { title: 'Ledger', detail: 'goal, facts, assumptions, constraints, unknowns' },
    { title: 'Search', detail: 'tournament rounds: deepen clear winners, re-judge close calls' },
    { title: 'Verify', detail: 'check terminal claims with real verifiers' },
    { title: 'Refute', detail: 'independent skeptics attack the chosen path' },
    { title: 'Synthesize', detail: 'answer that survived refutation' },
  ],
}

// ---------- input ----------
const TASK = typeof args === 'string' ? args : (args && args.task) || ''
if (!TASK) throw new Error('reasontree-verify: pass the task as args, e.g. /reasontree-verify <your problem>')
const OPT = typeof args === 'object' && args ? args : {}
const DEPTH = Math.min(OPT.depth || 3, 5)
const WIDTH = Math.min(OPT.width || 3, 5)
const MAX_NODES = OPT.max_nodes || 18
const GAP_CLEAR = 2.0      // pathScore gap that makes a winner "clear"
const GOOD_ENOUGH = 8.0    // terminal claims at/above this get a verifier
const DIVERSITY_MARGIN = 2.0
const EFFORT = OPT.effort
const MODEL = OPT.model

function aopts(label, phaseName, schema) {
  const o = { label: label, phase: phaseName, schema: schema }
  if (EFFORT) o.effort = EFFORT
  if (MODEL) o.model = MODEL
  return o
}

// ---------- schemas ----------
const LEDGER_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    goal: { type: 'string' },
    initial_state: { type: 'string' },
    facts: { type: 'array', items: { type: 'string' } },
    assumptions_or_beliefs: { type: 'array', items: { type: 'string' } },
    hard_constraints: { type: 'array', items: { type: 'string' } },
    user_preferences: { type: 'array', items: { type: 'string' } },
    uncertainties: { type: 'array', items: { type: 'string' } },
    success_criteria: { type: 'array', items: { type: 'string' } },
  },
  required: ['goal', 'initial_state', 'facts', 'assumptions_or_beliefs', 'hard_constraints', 'user_preferences', 'uncertainties', 'success_criteria'],
}

const EXPAND_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    branches: {
      type: 'array',
      minItems: 1,
      maxItems: 5,
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          action: { type: 'string' },
          next_state: { type: 'string' },
          score: { type: 'number', minimum: 0, maximum: 10 },
          terminal: { type: 'boolean' },
          rationale: { type: 'string' },
          facts_used: { type: 'array', items: { type: 'string' } },
          assumptions_used: { type: 'array', items: { type: 'string' } },
          beliefs_tested: { type: 'array', items: { type: 'string' } },
          failure_modes: { type: 'array', items: { type: 'string' } },
        },
        required: ['action', 'next_state', 'score', 'terminal', 'rationale', 'facts_used', 'assumptions_used', 'beliefs_tested', 'failure_modes'],
      },
    },
    node_note: { type: 'string' },
  },
  required: ['branches', 'node_note'],
}

const REJUDGE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    rescored: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          id: { type: 'number' },
          score: { type: 'number', minimum: 0, maximum: 10 },
          rationale: { type: 'string' },
        },
        required: ['id', 'score', 'rationale'],
      },
    },
    judge_note: { type: 'string' },
  },
  required: ['rescored', 'judge_note'],
}

const VERIFY_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    verified: { type: 'boolean' },
    confidence: { type: 'number', minimum: 0, maximum: 1 },
    evidence: { type: 'string', description: 'what was actually checked and what it showed' },
    corrected_score: { type: 'number', minimum: 0, maximum: 10 },
    failure_note: { type: 'string', description: 'if not verified: the concrete reason, phrased so other branches can avoid it' },
  },
  required: ['verified', 'confidence', 'evidence', 'corrected_score', 'failure_note'],
}

const REFUTE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    refuted: { type: 'boolean', description: 'true if the path has a flaw serious enough to change the answer' },
    severity: { type: 'number', minimum: 0, maximum: 10 },
    objection: { type: 'string', description: 'the strongest concrete objection found, or why the path survives' },
    evidence: { type: 'string', description: 'what was checked (tool output, fact, constraint) that supports the objection' },
    fix_if_any: { type: 'string' },
  },
  required: ['refuted', 'severity', 'objection', 'evidence', 'fix_if_any'],
}

const FINAL_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    final_answer: { type: 'string' },
    best_next_action: { type: 'string' },
    why: { type: 'string' },
    path: { type: 'array', items: { type: 'string' } },
    runner_up: { type: 'string' },
    key_assumptions: { type: 'array', items: { type: 'string' } },
    failure_check: { type: 'string' },
    confidence: { type: 'number', minimum: 0, maximum: 1 },
  },
  required: ['final_answer', 'best_next_action', 'why', 'path', 'runner_up', 'key_assumptions', 'failure_check', 'confidence'],
}

// ---------- prompt helpers ----------
const SCORING_GUIDE = [
  'Score siblings TOGETHER on one 0-10 scale, comparing them against each other:',
  '- 0-2: violates a hard constraint, contradicts a stated fact, or provably fails',
  '- 3-4: plausible but rests on untested assumptions with no supporting fact',
  '- 5-6: reasonable, partially supported, meaningful open risks',
  '- 7-8: strongly supported by stated facts or a verifier check, minor risks',
  '- 9-10: verified or near-certain to achieve the goal; reserve 10 for checked results',
  'Spread the scores: if two siblings are not equally good, their scores must differ.',
].join('\n')

const VERIFY_HINT = [
  'If the task involves anything checkable (code, math, logic, schedules, game positions, dates, file contents),',
  'you MAY use your tools (Bash, Read, web) to actually verify before scoring.',
  'A branch confirmed by a real check outranks any unverified branch. Never fabricate a verification.',
].join('\n')

function ledgerBlock(ledger) {
  return [
    'GOAL: ' + ledger.goal,
    'FACTS (verified/stated): ' + JSON.stringify(ledger.facts),
    'ASSUMPTIONS/BELIEFS (unverified): ' + JSON.stringify(ledger.assumptions_or_beliefs),
    'HARD CONSTRAINTS: ' + JSON.stringify(ledger.hard_constraints),
    'USER PREFERENCES: ' + JSON.stringify(ledger.user_preferences),
    'UNCERTAINTIES: ' + JSON.stringify(ledger.uncertainties),
    'SUCCESS CRITERIA: ' + JSON.stringify(ledger.success_criteria),
  ].join('\n')
}

function pathBlock(node) {
  const steps = []
  let cur = node
  while (cur && cur.parent) {
    steps.unshift('- action: ' + cur.action + ' -> state: ' + cur.next_state)
    cur = cur.parent
  }
  return steps.length ? steps.join('\n') : '(root: no actions taken yet)'
}

// ---------- tree ----------
let nextId = 1
function makeNode(parent, branch) {
  const scores = []
  let cur = parent
  while (cur && cur.parent) { scores.push(cur.score); cur = cur.parent }
  const node = {
    id: nextId++,
    parent: parent,
    depth: parent ? parent.depth + 1 : 0,
    action: branch.action,
    next_state: branch.next_state,
    score: branch.score,
    terminal: branch.terminal,
    rationale: branch.rationale,
    facts_used: branch.facts_used,
    assumptions_used: branch.assumptions_used,
    beliefs_tested: branch.beliefs_tested,
    failure_modes: branch.failure_modes,
    verifier: null,
    children: [],
  }
  if (parent) parent.children.push(node)
  recomputePathScore(node)
  return node
}

function recomputePathScore(node) {
  const scores = []
  let cur = node
  while (cur && cur.parent) { scores.push(cur.score); cur = cur.parent }
  node.pathScore = scores.reduce((a, b) => a + b, 0) / scores.length
}

function credibleTerminal(node) {
  return Boolean(node.terminal && node.score >= GOOD_ENOUGH)
}

function rootAncestor(node) {
  let cur = node
  while (cur.parent && cur.parent.parent) cur = cur.parent
  return cur
}

function pathActions(node) {
  const acts = []
  let cur = node
  while (cur && cur.parent) { acts.unshift(cur.action); cur = cur.parent }
  return acts
}

// ---------- phase 1: ledger ----------
phase('Ledger')
log('Building context ledger')
const ledger = (await agent(

  [
    'You are the context-ledger builder for a bounded reasoning tree.',
    'Read the task below and extract a precise context ledger.',
    'Separate FACTS (stated or verifiable) from ASSUMPTIONS (plausible but unverified). Do not invent facts.',
    'If the task involves checkable artifacts (files, code, positions, numbers), you may use tools to verify facts first.',
    '',
    'TASK:',
    TASK,
  ].join('\n'),
  aopts('ledger', 'Ledger', LEDGER_SCHEMA)
)) || {
  goal: 'Answer the task correctly: ' + TASK.slice(0, 200),
  initial_state: 'Task as given (ledger agent unavailable): ' + TASK.slice(0, 600),
  facts: [], assumptions_or_beliefs: [], hard_constraints: [],
  user_preferences: [], uncertainties: ['context ledger could not be built; verify claims directly against the task text'],
  success_criteria: ['the final answer directly and correctly answers the task'],
}

// ---------- expansion helper ----------
const failureNotes = []
const crossTreeNotes = []
let nodesExpanded = 0
let totalNodes = 0

async function expandNode(node, level) {
  const res = await agent(
    [
      'You are one expansion step inside a bounded reasoning tree (depth ' + level + ' of ' + DEPTH + ').',
      'Given the context ledger, the path taken so far, and the current state,',
      'propose exactly ' + WIDTH + ' DISTINCT candidate next actions. Then score them together.',
      '',
      ledgerBlock(ledger),
      '',
      'ORIGINAL TASK:',
      TASK,
      '',
      'PATH SO FAR:',
      pathBlock(node),
      '',
      'CURRENT STATE: ' + node.next_state,
      '',
      failureNotes.length ? 'KNOWN DEAD-ENDS / FAILURE NOTES FROM OTHER BRANCHES (do not repeat these):\n- ' + failureNotes.slice(-8).join('\n- ') : '',
      '',
      SCORING_GUIDE,
      '',
      VERIFY_HINT,
      '',
      'Mark a branch terminal:true ONLY if that action fully answers the original task.',
      'Keep every field short. Rationale max 2 sentences.',
    ].join('\n'),
    aopts('expand:d' + level + ':n' + node.id, 'Search', EXPAND_SCHEMA)
  )
  if (!res || !res.branches) return []
  nodesExpanded++
  if (res.node_note) crossTreeNotes.push(res.node_note)
  const children = res.branches.slice(0, WIDTH).map(b => {
    const c = makeNode(node, b)
    totalNodes++
    b.failure_modes.forEach(f => { if (f && failureNotes.length < 40) failureNotes.push(f) })
    return c
  })
  return children
}

// ---------- verifier helper ----------
async function verifyTerminal(node) {
  const v = await agent(
    [
      'You are the VERIFIER of a reasoning tree. A branch claims it fully solves the task. Check it for real.',
      'Use your tools (Bash, python, Read, web) to actually verify wherever possible:',
      'for games or puzzles use a suitable solver library, for math compute it, for code run it, for logic enumerate cases.',
      'If you cannot verify mechanically, stress-test the claim against the facts and hard constraints.',
      'Be adversarial: your job is to catch a wrong answer before it ships. Never rubber-stamp.',
      '',
      ledgerBlock(ledger),
      '',
      'ORIGINAL TASK:',
      TASK,
      '',
      'CLAIMED SOLUTION PATH:',
      pathBlock(node),
      '',
      'CLAIMED FINAL ACTION: ' + node.action,
      'CLAIMED RESULT: ' + node.next_state,
      'CLAIMED RATIONALE: ' + node.rationale,
    ].join('\n'),
    aopts('verify:n' + node.id, 'Verify', VERIFY_SCHEMA)
  )
  if (!v) return { verified: false, confidence: 0, evidence: 'verifier failed', corrected_score: node.score, failure_note: '' }
  return v
}

// ---------- phase 2: tournament search ----------
phase('Search')
const root = {
  id: 0, parent: null, depth: 0, action: null,
  next_state: ledger.initial_state, score: 0, terminal: false,
  children: [], pathScore: 0, verifier: null,
}
let frontier = [root]
let verifiedWinner = null
let rejudgeRounds = 0

for (let level = 1; level <= DEPTH && !verifiedWinner; level++) {
  const expandable = frontier.filter(n => !n.terminal)
  if (!expandable.length || totalNodes >= MAX_NODES) break
  log('Round ' + level + ': expanding ' + expandable.length + ' node(s)')

  const childSets = await parallel(expandable.map(n => () => expandNode(n, level)))
  const contenders = childSets.filter(Boolean).flat()
  if (!contenders.length) break

  // verify terminal claims (strongest first, at most 2 per round)
  const terminalClaims = contenders.filter(c => c.terminal && c.score >= GOOD_ENOUGH)
    .sort((a, b) => b.pathScore - a.pathScore).slice(0, 2)
  if (terminalClaims.length) {
    log('Verifying ' + terminalClaims.length + ' terminal claim(s)')
    const verdicts = await parallel(terminalClaims.map(c => () => verifyTerminal(c)))
    verdicts.forEach((v, i) => {
      const c = terminalClaims[i]
      if (!v) return
      c.verifier = v
      if (v.verified && v.confidence >= 0.7) {
        if (!verifiedWinner || c.pathScore > verifiedWinner.pathScore) verifiedWinner = c
      } else {
        c.score = Math.min(c.score, v.corrected_score)
        c.terminal = false
        recomputePathScore(c)
        if (v.failure_note && failureNotes.length < 40) failureNotes.push(v.failure_note)
        log('Terminal claim rejected by verifier: ' + (v.failure_note || 'no note'))
      }
    })
    if (verifiedWinner) { log('Verified winner found - stopping search'); break }
  }

  // tournament selection among non-terminal contenders
  const alive = contenders.filter(c => !c.terminal)
  if (!alive.length) break
  const sorted = alive.slice().sort((a, b) => (b.pathScore - a.pathScore) || (b.score - a.score))
  const top1 = sorted[0]
  const top2 = sorted[1]
  const gap = top2 ? top1.pathScore - top2.pathScore : 99

  if (gap >= GAP_CLEAR || !top2) {
    frontier = [top1]
    log('Clear winner (gap ' + gap.toFixed(1) + '): deepening only "' + top1.action.slice(0, 60) + '"')
  } else {
    // close call: fresh-eyes comparative re-judge of the top contenders
    rejudgeRounds++
    const closeSet = sorted.filter(c => top1.pathScore - c.pathScore <= DIVERSITY_MARGIN).slice(0, 4)
    log('Close call (gap ' + gap.toFixed(1) + '): re-judging ' + closeSet.length + ' contenders with fresh eyes')
    const rj = await agent(
      [
        'You are a fresh-eyes JUDGE inside a reasoning tree tournament. Several candidate branches scored too close to call.',
        'Compare them jointly and re-score each on the same 0-10 scale. You may use tools to check claims.',
        'Do NOT anchor on the previous scores; judge the branches on their merits against the goal and constraints.',
        '',
        ledgerBlock(ledger),
        '',
        'ORIGINAL TASK:',
        TASK,
        '',
        'CONTENDERS:',
        closeSet.map(c => JSON.stringify({
          id: c.id,
          path: pathActions(c),
          resulting_state: c.next_state,
          previous_score: c.score,
          rationale: c.rationale,
          failure_modes: c.failure_modes,
        })).join('\n'),
        '',
        SCORING_GUIDE,
      ].join('\n'),
      aopts('rejudge:r' + level, 'Search', REJUDGE_SCHEMA)
    )
    if (rj && rj.rescored) {
      rj.rescored.forEach(r => {
        const c = closeSet.find(x => x.id === r.id)
        if (c) { c.score = r.score; c.rationale = c.rationale + ' | judge: ' + r.rationale; recomputePathScore(c) }
      })
      if (rj.judge_note) crossTreeNotes.push('judge: ' + rj.judge_note)
    }
    const resorted = closeSet.slice().sort((a, b) => (b.pathScore - a.pathScore) || (b.score - a.score))
    frontier = resorted.slice(0, 2)
    // diversity: if both survivors share a root ancestor and a rival is close, add it
    const anchors = new Set(frontier.map(c => rootAncestor(c).id))
    if (anchors.size === 1) {
      const rival = sorted.find(c => !anchors.has(rootAncestor(c).id) &&
        frontier[frontier.length - 1].pathScore - c.pathScore <= DIVERSITY_MARGIN)
      if (rival) { frontier.push(rival); log('Keeping one diverse rival path') }
    }
  }
}

// ---------- pick best + runner-up ----------
function leaves(node, acc) {
  if (!node.children.length) { if (node.parent) acc.push(node); return acc }
  node.children.forEach(c => leaves(c, acc))
  return acc
}
const allLeaves = leaves(root, [])
if (!allLeaves.length) throw new Error('reasontree: tree has no branches')
const ranked = allLeaves.slice().sort((a, b) =>
  (Number(Boolean(b.verifier && b.verifier.verified)) - Number(Boolean(a.verifier && a.verifier.verified))) ||
  (Number(credibleTerminal(b)) - Number(credibleTerminal(a))) ||
  (b.depth - a.depth) ||
  (b.pathScore - a.pathScore) || (b.score - a.score))
let best = verifiedWinner || ranked[0]
const bestAnchor = rootAncestor(best).id
let runnerUp = ranked.find(l => l !== best && rootAncestor(l).id !== bestAnchor) || ranked.find(l => l !== best) || null

// ---------- phase 3: adversarial refutation ----------
phase('Refute')
const REFUTE_LENSES = [
  { key: 'grounding', prompt: 'FACTUAL GROUNDING: check every claim in the path against the stated facts and against reality. Use tools (Bash, python, web) to actually re-verify anything checkable. A single fabricated or unsupported factual claim is a refutation.' },
  { key: 'constraints', prompt: 'CONSTRAINTS AND RISKS: check the path against every hard constraint, user preference, and success criterion in the ledger. Look for the hidden constraint the path silently violates and the failure mode nobody scored.' },
  { key: 'alternatives', prompt: 'ALTERNATIVE SUPERIORITY: argue the runner-up (or a path nobody explored) is actually better. If a materially better alternative exists, that refutes the chosen path.' },
]

async function refutePath(node, tag) {
  const votes = await parallel(REFUTE_LENSES.map(lens => () => agent(
    [
      'You are an independent SKEPTIC reviewing the chosen answer of a reasoning tree. Your job is to REFUTE it if you can.',
      'Default to refuted=false only if the path genuinely survives your attack. Do not invent weak objections to look busy;',
      'severity >= 6 must mean "this changes the answer".',
      '',
      'YOUR LENS - ' + lens.prompt,
      '',
      ledgerBlock(ledger),
      '',
      'ORIGINAL TASK:',
      TASK,
      '',
      'CHOSEN PATH:',
      pathBlock(node),
      'Rationale: ' + node.rationale,
      node.verifier ? 'Verifier said: verified=' + node.verifier.verified + ', evidence: ' + node.verifier.evidence : 'No mechanical verification was possible during search.',
      '',
      'RUNNER-UP PATH (for the alternatives lens):',
      runnerUp ? pathBlock(runnerUp) : '(none)',
    ].join('\n'),
    aopts('refute:' + lens.key + ':' + tag, 'Refute', REFUTE_SCHEMA)
  )))
  return votes.filter(Boolean)
}

log('Refuting chosen path with ' + REFUTE_LENSES.length + ' independent skeptics')
let objections = await refutePath(best, 'primary')
let refutedCount = objections.filter(o => o.refuted && o.severity >= 6).length
let pathSwitched = false

if (refutedCount >= 2 && runnerUp) {
  log('Chosen path refuted by ' + refutedCount + ' skeptics - trying runner-up')
  objections.forEach(o => { if (o.refuted && o.objection && failureNotes.length < 40) failureNotes.push(o.objection) })
  const rObjections = await refutePath(runnerUp, 'runnerup')
  const rRefuted = rObjections.filter(o => o.refuted && o.severity >= 6).length
  const severity = objs => objs.reduce((s, o) => s + (o.refuted ? o.severity : 0), 0)
  if (rRefuted < refutedCount || severity(rObjections) < severity(objections)) {
    const oldBest = best
    best = runnerUp
    runnerUp = oldBest
    objections = rObjections
    pathSwitched = true
    log('Switched to runner-up path (it survived refutation better)')
  }
}

// ---------- phase 4: synthesis ----------
phase('Synthesize')
log('Synthesizing final answer (' + nodesExpanded + ' expansions, ' + totalNodes + ' branches, ' + rejudgeRounds + ' re-judge rounds)')
const final = await agent(
  [
    'You are the synthesis step of a bounded reasoning tree. The search is done; commit to an answer.',
    'Use the SELECTED PATH as the backbone, but check it against the runner-up and the cross-tree notes.',
    'If the evidence is weak, say so honestly in failure_check and lower confidence. Never oversell.',
    'final_answer must directly answer the ORIGINAL TASK in exactly the format the task asked for',
    '(e.g. if it asked for a single move or value, final_answer is just that; if it asked for a decision, the decision).',
    '',
    ledgerBlock(ledger),
    '',
    'ORIGINAL TASK:',
    TASK,
    '',
    'SELECTED PATH (pathScore ' + best.pathScore.toFixed(1) + ', terminal=' + best.terminal + (best.verifier ? ', VERIFIED: ' + best.verifier.verified + ' conf ' + best.verifier.confidence : ', unverified') + '):',
    pathBlock(best),
    'Selected path rationale: ' + best.rationale,
    best.verifier ? 'Verifier evidence: ' + best.verifier.evidence : '',
    'Selected path failure modes: ' + JSON.stringify(best.failure_modes || []),
    '',
    'RUNNER-UP PATH' + (runnerUp ? ' (pathScore ' + runnerUp.pathScore.toFixed(1) + '):' : ': (none)'),
    runnerUp ? pathBlock(runnerUp) : '',
    '',
    'CROSS-TREE NOTES:',
    crossTreeNotes.slice(0, 12).map(n => '- ' + n).join('\n') || '(none)',
    '',
    'FAILURE NOTES COLLECTED ACROSS BRANCHES:',
    failureNotes.slice(0, 12).map(n => '- ' + n).join('\n') || '(none)',
    '',
    'ADVERSARIAL REVIEW OF THE SELECTED PATH (' + (pathSwitched ? 'note: original winner was refuted, this is the surviving path' : 'path survived') + '):',
    objections.map(o => '- [' + (o.refuted ? 'REFUTED sev ' + o.severity : 'survived') + '] ' + o.objection + (o.fix_if_any ? ' | fix: ' + o.fix_if_any : '')).join('\n') || '(none)',
    'Weave surviving objections into failure_check; if a fix was suggested, apply it to the final answer when it clearly improves it.',
  ].join('\n'),
  aopts('synthesize', 'Synthesize', FINAL_SCHEMA)
)
if (!final) throw new Error('reasontree: synthesis agent failed')

const answerMarkdown = [
  '**Best next action:** ' + final.best_next_action,
  '',
  '**Why:** ' + final.why,
  '',
  '**ReasonTree path:**',
  final.path.map((s, i) => (i + 1) + '. ' + s).join('\n'),
  '',
  '**Runner-up:** ' + final.runner_up,
  '',
  '**Key assumptions:** ' + final.key_assumptions.join('; '),
  '',
  '**Failure check:** ' + final.failure_check,
  '',
  '_Confidence: ' + final.confidence.toFixed(2) + ' | expansions: ' + nodesExpanded + ' | branches: ' + totalNodes + ' | verified winner: ' + Boolean(verifiedWinner) + '_',
].join('\n')

return {
  variant: 'verify',
  final_answer: final.final_answer,
  decision: final,
  answer_markdown: answerMarkdown,
  stats: {
    nodes_expanded: nodesExpanded,
    branches_created: totalNodes,
    rejudge_rounds: rejudgeRounds,
    verified_winner: Boolean(verifiedWinner),
    refuted_count: refutedCount,
    path_switched: pathSwitched,
    depth_reached: best.depth,
    best_path_score: best.pathScore,
  },
  best_path: pathActions(best),
  runner_up_path: runnerUp ? pathActions(runnerUp) : [],
}
