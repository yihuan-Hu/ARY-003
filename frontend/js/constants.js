(function () {
  function statusLabel(status) {
    const labels = {
      draft: '草稿',
      published: '已发布',
      registration: '报名中',
      submitted: '已提交',
      approved: '已通过',
      rejected: '已拒绝',
      running: '进行中',
      submitting: '作品提交',
      judging: '评审中',
      completed: '已完成',
      archived: '已归档',
      withdrawn: '已撤回',
    };
    return labels[status] || status || '未知';
  }

  function nextRaceActionLabel(status) {
    const labels = {
      draft: '下一步：发布赛事，让参赛者能看到赛事详情。',
      published: '下一步：开放报名，开始收集参赛申请。',
      registration: '下一步：审核报名，通过后可启动比赛。',
      running: '下一步：开放作品提交，让骑手提交参赛作品。',
      submitting: '下一步：开始评审，锁定作品并通知评委。',
      judging: '下一步：完成评审并发布最终结果。',
      completed: '下一步：归档赛事，锁定历史结果。',
      archived: '赛事已归档，状态不可再推进。',
    };
    return labels[status] || '暂无可执行的状态动作。';
  }

  window.ARYConstants = { statusLabel, nextRaceActionLabel };
})();
