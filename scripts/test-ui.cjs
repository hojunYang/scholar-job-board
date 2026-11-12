const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const Database = require('better-sqlite3');
const root = path.resolve(__dirname, '..');
const db = new Database(path.join(root, 'data/scholar.db'), { readonly: true });
function load(relative) {
  const source = fs.readFileSync(path.join(root, relative), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { esModuleInterop: true, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
  const module = { exports: {} };
  new Function('require', 'exports', 'module', compiled)(name => {
    if (name === './eligibility') return load('lib/eligibility.ts');
    if (name.startsWith('@/data/')) return require(path.join(root,name.replace('@/', '')));
    if (name === './db') return { getDb: () => db };
    return require(name);
  }, module.exports, module);
  return module.exports;
}
try {
  const { deadlineInfo } = load('lib/notice-ui.ts');
  const queries = load('lib/queries.ts');
  const { parseProfile, profileFields, profileSql } = load('lib/eligibility.ts');
  assert.ok(profileFields('장학·학비지원').includes('incomeTier'));
  assert.ok(!profileFields('취업·인턴·현장실습').includes('incomeTier'));
  assert.ok(profileFields('취업·인턴·현장실습','현장실습').includes('studentYear'));
  assert.deepEqual(parseProfile({incomeTier:'4',degreeLevel:'bachelor'},'취업·인턴·현장실습'),{degreeLevel:'bachelor'});
  assert.deepEqual(parseProfile({studentYear:'2'},'장학·학비지원'),{studentYear:'2',studyLevel:'undergraduate'});
  for (const category of ['장학·학비지원','근로·알바·학생조교','취업·인턴·현장실습']) {
    const profile=category==='취업·인턴·현장실습'?{degreeLevel:'bachelor'}:{studentYear:'2'};
    for(const status of [undefined,'closed']) {
      const filter={mainCategory:category,status,profile};
      const strict=queries.getNotices(filter);
      assert.equal(strict.length,queries.getNoticeCount(filter));
      assert.ok(strict.every(row=>row.eligibilityMatch==='matched'));
      const loose=queries.getNotices({...filter,profile:{...profile,includeUnknown:'1'}});
      assert.ok(loose.length>=strict.length);
      assert.equal(queries.getCategoryCounts(filter).reduce((n,row)=>n+row.count,0),strict.length);
    }
  }
  function matches(profile, values) {
    const filter=profileSql(profile);
    const columns={student_years:'[2,3,4]',income_tiers:'["0","1","2","3","4"]',degree_levels:'["bachelor","master","doctorate"]',gpa_minima:'{"4.5":3.0}',field_states:'{"studentYear":"known","incomeTier":"known","degreeLevel":"known","gpa":"known"}',...values};
    return db.prepare(`SELECT COUNT(*) AS n FROM (SELECT ${Object.keys(columns).map(k=>`? AS ${k}`).join(',')}) eligibility WHERE ${filter.sql}`).get(...Object.values(columns),...filter.params).n===1;
  }
  assert.ok(matches({studentYear:'2'}));
  assert.ok(!matches({studentYear:'1'}));
  assert.ok(matches({incomeTier:'4'}));
  assert.ok(!matches({incomeTier:'5'}));
  assert.ok(matches({degreeLevel:'bachelor'}));
  assert.ok(!matches({degreeLevel:'associate'}));
  assert.ok(matches({gpa:'3.2',gpaScale:'4.5'}));
  assert.ok(!matches({gpa:'2.8',gpaScale:'4.5'}));
  assert.ok(!matches({gpa:'3.2',gpaScale:'4.3'}));
  assert.ok(matches({gpa:'3.2',gpaScale:'4.3',includeUnknown:'1'}));
  for (const board of queries.getNoticeBoards()) {
    for (const status of [undefined,'closed']) {
      const filter={source:board.id,status};
      const rows=queries.getNotices(filter);
      assert.equal(rows.length,queries.getNoticeCount(filter));
      assert.equal(rows.length,queries.getCategoryCounts(filter).reduce((n,row)=>n+row.count,0));
      for (const row of rows) assert.ok(db.prepare('SELECT 1 FROM notice_origins WHERE notice_id=? AND board_id=?').get(row.id,board.id));
    }
    assert.equal(queries.getBoardStats({source:board.id}).total,queries.getNoticeCount({source:board.id}));
  }
  assert.equal(queries.getNoticeCount({source:"' OR 1=1 --"}),0);
  const departmentRows=queries.getNotices({source:'cse-undergraduate'});
  assert.ok(departmentRows.length>0);
  assert.ok(departmentRows.every(row=>row.sourceLabels.includes('소프트웨어학과')));
  const departmentDetail=queries.getJobById(departmentRows[0].id);
  assert.ok(departmentDetail.origins.some(origin=>origin.boardId==='cse-undergraduate' && origin.url.startsWith('https://cse.skku.edu/')));
  const noon = Date.parse('2026-11-12T12:00:00+09:00');
  assert.equal(deadlineInfo('2026-11-12', noon).label, '오늘 마감');
  assert.equal(deadlineInfo('2026-11-13', noon).label, 'D-1');
  assert.equal(deadlineInfo('2026-11-11', noon).state, 'closed');
  assert.equal(deadlineInfo('2026-11-12T03:30:00Z', noon).label, '오늘 마감');
  assert.equal(deadlineInfo('채용 시 마감', noon).state, 'rolling');
  assert.equal(deadlineInfo('미정', noon).state, 'unknown');
  assert.equal(deadlineInfo('2027-12-31', noon, '', 'needs_review').state, 'closed');
  assert.equal(deadlineInfo('상시', noon, '', 'pending').state, 'closed');
  assert.equal(queries.getNoticeCount({ query: "%' OR 1=1 --" }), 0);
  assert.equal(queries.getNoticeCount({ query: '%' }), queries.getNotices({ query: '%' }).length);
  const filters = { mainCategory: '장학·학비지원', subcategory: '생활비 장학', audience: '소득', status: 'closed' };
  const results = queries.getNotices(filters);
  assert.ok(results.length > 0);
  assert.equal(results.length, queries.getNoticeCount(filters));
  for (const row of results) {
    assert.equal(row.main_category, filters.mainCategory);
    assert.equal(row.subcategory, filters.subcategory);
    assert.ok(`${row.target_audience} ${row.eligibility_conditions}`.includes('소득'));
  }
  const active = queries.getNotices();
  const closed = queries.getNotices({ status: 'closed' });
  const archiveSize = db.prepare('SELECT COUNT(*) AS n FROM notices').get().n;
  assert.equal(active.length + closed.length, archiveSize);
  const closedIds = new Set(closed.map(row => row.id));
  assert.ok(closedIds.size > 0);
  assert.ok(active.every(row => !closedIds.has(row.id)));
  assert.ok(active.every(row => deadlineInfo(row.deadline, Date.now(), row.title, row.classification_status).state !== 'closed'));
  assert.ok(closed.every(row => deadlineInfo(row.deadline, Date.now(), row.title, row.classification_status).state === 'closed'));
  assert.equal(queries.getBoardStats().total, active.length);
  assert.equal(queries.getCategoryCounts().reduce((sum, row) => sum + row.count, 0), active.length);
  assert.equal(queries.getCategoryCounts({ status: 'closed' }).reduce((sum, row) => sum + row.count, 0), closed.length);
  const soon = queries.getNotices({ status: 'closing-soon' });
  for (const row of soon) assert.equal(deadlineInfo(row.deadline).state, 'soon');
  const reviewed = queries.getNotices({ review: true, status: 'closed' });
  assert.equal(reviewed.length, db.prepare("SELECT COUNT(*) AS n FROM notices WHERE classification_status IN ('needs_review', 'pending')").get().n);
  assert.ok(reviewed.every(row => closedIds.has(row.id)));
  assert.ok(active.every(row => !['needs_review', 'pending'].includes(row.classification_status)));
  assert.ok(reviewed.every(row => ['needs_review', 'pending'].includes(row.classification_status)));
  assert.equal(queries.getNotices({ limit: 12 }).length, 12);
  assert.equal(new Set(queries.getNotices().map(row => row.id)).size, queries.getNoticeCount());
  const detail = queries.getJobById(141133);
  assert.ok(detail);
  assert.ok(detail.attachments.every(row => /^https?:\/\//i.test(row.downloadPath)));
  console.log(`Counts: default ${active.length}; closed tab ${closed.length}; archive ${archiveSize}`);
  console.log('UI integration checks passed: filters, literal search, counts, paging, KST deadlines, attachment URLs.');
} finally {
  db.close();
}
