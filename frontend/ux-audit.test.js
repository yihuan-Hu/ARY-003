const fs = require('fs');
const assert = require('assert');

const app = fs.readFileSync('frontend/app.js', 'utf8');
const html = fs.readFileSync('frontend/index.html', 'utf8');

assert(app.includes("case 'riders'"), 'Riders navigation must have an explicit page-load branch');
assert(!app.includes('/race-projects/${reg.id}'), 'Dashboard must not use registration.id as race_project_id');
assert(app.includes('loadRaceProjectForRegistration'), 'Dashboard should resolve RaceProject from registration detail');
assert(app.includes('judgeInvitations'), 'Dashboard should load judge invitations');
assert(app.includes('acceptJudgeInvitation'), 'Accepting judge invitations should be wired');
assert(app.includes('openRiderProfile'), 'Leaderboard/work cards should be able to open rider profiles');

assert(html.includes('我参与的比赛'), 'Nav/dashboard must expose the participation tab in Chinese');
assert(html.includes('我组织的比赛'), 'Nav/admin must expose the organizer tab in Chinese');
assert(!html.includes('v-if="isOrganizer" :class="{active: currentPage===\'admin\'}"'), 'Organizer tab must not be hidden by role');
assert(html.includes('报名记录'), 'Dashboard must surface registrations');
assert(html.includes('评委邀请'), 'Dashboard must surface judge invitations');
assert(html.includes('接受后进入评审清单'), 'Judge invitation accept flow should explain the redirect');
assert(html.includes('nextRaceActionLabel'), 'Organizer race cards should show the next status action guide');
assert(html.includes('已登录'), 'Register page should not show the static signup form to logged-in users');

console.log('UX audit static checks passed');
