(function () {
  function register(app) {
    app.component('metric-card', {
      props: ['label', 'value'],
      template: `
        <article class="state-card metric-card">
          <span>{{ label }}</span>
          <b>{{ value }}</b>
        </article>
      `,
    });

    app.component('task-card', {
      props: ['title', 'desc', 'status'],
      template: `
        <article class="glass-card task-card">
          <span v-if="status" class="status-note">{{ status }}</span>
          <h3>{{ title }}</h3>
          <p>{{ desc }}</p>
          <slot></slot>
        </article>
      `,
    });

    app.component('page-state', {
      props: ['title', 'message', 'kind'],
      template: `
        <div :class="kind || 'empty-state'">
          <h2>{{ title }}</h2>
          <p v-if="message">{{ message }}</p>
          <slot></slot>
        </div>
      `,
    });
  }

  window.ARYComponents = { register };
})();
