(function () {
  const iconMap = {
    new_event: '&#127881;',
    event_approved: '&#9989;',
    approval: '&#9989;',
    event_rejected: '&#10060;',
    rejection: '&#10060;',
    registration_confirmed: '&#128221;',
    registration: '&#128221;',
    event_reminder: '&#9200;',
    reminder: '&#9200;',
    expiry: '&#9200;',
    new_submission: '&#128276;'
  };

  function timeAgo(value) {
    const then = new Date(value).getTime();
    if (!then) return 'just now';
    const seconds = Math.max(1, Math.floor((Date.now() - then) / 1000));
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.floor(hours / 24)}d ago`;
  }

  function ensureShell() {
    if (window.EventWorldStore && window.EventWorldStore.setupGlobalUi) {
      window.EventWorldStore.setupGlobalUi();
    }
    let bell = document.querySelector('.ew-bell');
    let panel = document.querySelector('.ew-notes');
    if (!bell) {
      bell = document.createElement('button');
      bell.type = 'button';
      bell.className = 'ew-bell';
      bell.innerHTML = '&#128276;<span class="ew-bell-count">0</span>';
      document.body.appendChild(bell);
    }
    if (!panel) {
      panel = document.createElement('div');
      panel.className = 'ew-notes';
      document.body.appendChild(panel);
    }
    return { bell, panel };
  }

  async function loadNotifications() {
    if (window.EventWorldAPI && window.EventWorldAPI.getNotifications) {
      return window.EventWorldAPI.getNotifications();
    }
    if (window.EventWorldStore && window.EventWorldStore.getNotifications) {
      return window.EventWorldStore.getNotifications();
    }
    return [];
  }

  async function markRead(id) {
    if (window.EventWorldAPI && window.EventWorldAPI.markRead) {
      await window.EventWorldAPI.markRead(id);
    }
  }

  async function markAllRead() {
    if (window.EventWorldAPI && window.EventWorldAPI.markAllRead) {
      await window.EventWorldAPI.markAllRead();
      return;
    }
    if (window.EventWorldStore && window.EventWorldStore.markAllRead) {
      window.EventWorldStore.markAllRead();
    }
  }

  async function renderNotifications() {
    const { bell, panel } = ensureShell();
    const notes = await loadNotifications();
    const unread = notes.filter(note => !note.read && !note.is_read).length;
    const badge = bell.querySelector('.ew-bell-count');
    if (badge) {
      badge.textContent = unread;
      badge.style.display = unread ? 'grid' : 'none';
    }
    panel.innerHTML = `
      <div class="ew-notes-head">
        <span>Notifications</span>
        <button type="button" id="ewSharedMarkRead">Mark all read</button>
      </div>
      ${notes.length ? notes.slice(0, 40).map(note => {
        const type = note.type || 'info';
        const eventId = note.eventId || note.event_id || '';
        const unreadClass = (!note.read && !note.is_read) ? ' unread' : '';
        return `
          <div class="ew-note${unreadClass}" data-note-id="${note.id || ''}" data-event-id="${eventId}" data-type="${type}">
            <strong>${iconMap[type] || '&#128276;'} ${note.title || 'Event World update'}</strong>
            <span>${note.message || ''} &middot; ${timeAgo(note.createdAt || note.created_at)}</span>
          </div>
        `;
      }).join('') : '<div class="ew-note"><span>No notifications yet</span></div>'}
    `;
    const mark = panel.querySelector('#ewSharedMarkRead');
    if (mark) mark.onclick = async () => {
      await markAllRead();
      await renderNotifications();
    };
    panel.querySelectorAll('.ew-note[data-note-id]').forEach(item => {
      item.onclick = async () => {
        const noteId = item.dataset.noteId;
        const eventId = item.dataset.eventId;
        const type = item.dataset.type;
        if (noteId) await markRead(noteId);
        if (eventId && type === 'event_rejected') {
          window.location.href = `submit-event.html?edit=${encodeURIComponent(eventId)}`;
        } else if (eventId) {
          window.location.href = `event-detail.html?id=${encodeURIComponent(eventId)}`;
        } else {
          window.location.href = 'admin.html';
        }
      };
    });
  }

  function initNotificationBell() {
    if (!document.querySelector('nav')) return;
    const { bell, panel } = ensureShell();
    bell.onclick = async () => {
      panel.classList.toggle('open');
      await renderNotifications();
    };
    renderNotifications();
    if (!window.EventWorldNotificationTimer) {
      window.EventWorldNotificationTimer = setInterval(renderNotifications, 30000);
    }
  }

  window.initNotificationBell = initNotificationBell;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initNotificationBell);
  } else {
    initNotificationBell();
  }
})();
