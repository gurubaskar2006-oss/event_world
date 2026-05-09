(function () {
  const keys = {
    pending: 'eventWorldPendingEvents',
    approved: 'eventWorldApprovedEvents',
    rejected: 'eventWorldRejectedEvents',
    expired: 'eventWorldExpiredEvents',
    archived: 'eventWorldArchivedEvents',
    registered: 'eventWorldRegisteredEvents',
    saved: 'eventWorldSavedEvents',
    session: 'eventWorldSession',
    notifications: 'eventWorldNotifications',
    views: 'eventWorldViewCounts'
  };

  const typeMeta = {
    hackathon: { banner: 'banner-hackathon', glow: 'hackathon-glow', icon: '⚡', mark: 'HK' },
    cultural: { banner: 'banner-cultural', glow: 'cultural-glow', icon: '🎭', mark: 'CF' },
    symposium: { banner: 'banner-symposium', glow: 'symposium-glow', icon: '🎯', mark: 'SP' },
    workshop: { banner: 'banner-workshop', glow: 'workshop-glow', icon: '🛠', mark: 'WS' }
  };
  const legacySeedIds = new Set([
    'hackfusion-2026',
    'saarang-cultural-fest',
    'techvista-2026',
    'ai-genai-bootcamp',
    'codestorm-2026',
    'ignite-2026'
  ]);

  function read(key, fallback) {
    try {
      const value = localStorage.getItem(key);
      return value ? JSON.parse(value) : fallback;
    } catch (error) {
      return fallback;
    }
  }

  function write(key, value) {
    localStorage.setItem(key, JSON.stringify(value));
  }

  function purgeLegacySeedEvents() {
    [keys.pending, keys.approved, keys.rejected].forEach(key => {
      const next = read(key, []).filter(eventItem => !legacySeedIds.has(eventItem && eventItem.id));
      write(key, next);
    });
    write(keys.registered, read(keys.registered, []).filter(item => !legacySeedIds.has(item && item.eventId)));
    write(keys.saved, read(keys.saved, []).filter(id => !legacySeedIds.has(id)));
    const views = read(keys.views, {});
    legacySeedIds.forEach(id => delete views[id]);
    write(keys.views, views);
  }

  function slugify(value) {
    return String(value || 'event')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/(^-|-$)/g, '') || 'event';
  }

  function parseEventDate(value) {
    if (!value) return null;
    if (/^\d{4}-\d{2}-\d{2}/.test(String(value))) {
      const parsedIso = new Date(`${String(value).slice(0, 10)}T00:00:00`);
      return Number.isNaN(parsedIso.getTime()) ? null : parsedIso;
    }
    const cleaned = String(value).split('-')[0].trim().replace(/(\d+)(st|nd|rd|th)/gi, '$1');
    const withYear = /\b\d{4}\b/.test(cleaned) ? cleaned : `${cleaned}, 2026`;
    const parsed = new Date(withYear);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }

  function prizeNumber(value) {
    const text = String(value || '').replace(/,/g, '');
    const match = text.match(/(\d+(?:\.\d+)?)/);
    if (!match) return 0;
    let amount = Number(match[1]);
    if (/lakh|lac/i.test(text)) amount *= 100000;
    if (/[kK]\b/.test(text)) amount *= 1000;
    return amount;
  }

  function registrationId() {
    return Math.random().toString(36).slice(2, 10).toUpperCase();
  }

  function coordinatorList(value) {
    if (!Array.isArray(value)) return [];
    return value.slice(0, 5).map(item => {
      const phone = String(item.phone || '').replace(/[^\d+]/g, '');
      const cleanPhone = phone.replace(/[^\d]/g, '');
      return {
        name: item.name || '',
        phone,
        whatsapp: item.whatsapp || (cleanPhone ? `https://wa.me/${cleanPhone}` : ''),
        email: item.email || ''
      };
    }).filter(item => item.name || item.phone || item.email);
  }

  function normalizeEvent(input, status) {
    input = input || {};
    const type = String(input.type || 'workshop').toLowerCase();
    const meta = typeMeta[type] || typeMeta.workshop;
    const title = input.title || input.eventName || 'Untitled Event';
    const id = input.id || `${slugify(title)}-${Date.now()}`;
    const tags = Array.isArray(input.tags)
      ? input.tags
      : String(input.tags || type).split(',').map(tag => tag.trim()).filter(Boolean);

    return {
      ...input,
      id,
      type,
      title,
      college: input.college || input.institution || 'Unknown Institution',
      desc: input.desc || input.description || 'Event details will be updated soon.',
      description: input.description || input.desc || 'Event details will be updated soon.',
      date: input.date || 'Date to be announced',
      time: input.time || 'Time to be announced',
      location: input.location || input.venue || 'Venue to be announced',
      fee: input.fee || 'Not announced',
      prize: input.prize || input.prizePool || 'Certificates',
      seats: input.seats || 'Seats open',
      team: input.team || input.teamSize || 'Individual / team',
      eligibility: input.eligibility || 'College students',
      mode: input.mode || 'Offline',
      contact: input.contact || input.email || 'organizer@eventworld.local',
      tags,
      posterBase64: input.posterBase64 || '',
      posterUrl: input.posterUrl || input.poster_url || null,
      websiteUrl: input.websiteUrl || '',
      coordinators: coordinatorList(input.coordinators),
      instagram: input.instagram || '',
      linkedin: input.linkedin || '',
      whatsappGroup: input.whatsappGroup || '',
      popularity: Number(input.popularity || input.registered || input.registeredCount || 0),
      highlights: input.highlights || 'This event is useful for networking, experience, certificates, and building your student profile.',
      schedule: input.schedule || [
        ['09:00 AM', 'Registration', 'Participants check in and receive event details.'],
        ['10:00 AM', 'Event begins', 'Main sessions and competitions start.'],
        ['04:00 PM', 'Results', 'Winners and certificates are announced.']
      ],
      colorA: input.colorA || (type === 'cultural' ? '#ff2d78' : type === 'symposium' ? '#00ff88' : type === 'workshop' ? '#ffd166' : '#7b2fff'),
      colorB: input.colorB || '#00f0ff',
      banner: input.banner || meta.banner,
      glow: input.glow || meta.glow,
      icon: input.icon || meta.icon,
      mark: input.mark || meta.mark,
      status: status || input.status || 'pending',
      submittedBy: input.submittedBy || input.ownerEmail || '',
      submittedAt: input.submittedAt || new Date().toISOString(),
      approvedAt: input.approvedAt || '',
      rejectedAt: input.rejectedAt || ''
    };
  }

  function getApprovedEvents() {
    const expiredIds = read(keys.expired, []);
    const archivedIds = read(keys.archived, []);
    const approved = read(keys.approved, []).map(eventItem => normalizeEvent(eventItem, 'approved'));
    return approved
      .filter(eventItem => !archivedIds.includes(eventItem.id))
      .map(eventItem => expiredIds.includes(eventItem.id) ? { ...eventItem, status: 'expired' } : eventItem);
  }

  function getPendingEvents() {
    return read(keys.pending, [])
      .map(eventItem => normalizeEvent(eventItem, eventItem.status || 'pending'))
      .filter(eventItem => eventItem.status === 'pending');
  }

  function getRejectedEvents() {
    const archivedIds = read(keys.archived, []);
    return read(keys.rejected, [])
      .map(eventItem => normalizeEvent(eventItem, 'rejected'))
      .filter(eventItem => eventItem.status === 'rejected' && !archivedIds.includes(eventItem.id));
  }

  function getSubmittedEvents() {
    return [...getPendingEvents(), ...read(keys.approved, []).map(eventItem => normalizeEvent(eventItem, 'approved')), ...getRejectedEvents()];
  }

  function submitEvent(eventInput) {
    const pending = getPendingEvents();
    const session = getSession();
    const eventItem = normalizeEvent({ ...eventInput, submittedBy: session && session.email }, 'pending');
    pending.push(eventItem);
    write(keys.pending, pending);
    return eventItem;
  }

  function approveEvent(id) {
    const pending = getPendingEvents();
    const eventItem = pending.find(event => event.id === id);
    if (!eventItem) return null;
    const approved = read(keys.approved, []);
    const liveEvent = { ...eventItem, status: 'approved', approvedAt: new Date().toISOString() };
    approved.push(liveEvent);
    write(keys.approved, approved);
    write(keys.pending, pending.filter(event => event.id !== id));
    addNotification(eventItem.submittedBy || 'institution', {
      title: `Your event ${eventItem.title} was approved!`,
      message: `${eventItem.title} is now live on Event World.`,
      eventId: eventItem.id,
      type: 'approval'
    });
    addNotification('all', {
      title: `New event near you: ${eventItem.title}`,
      message: `${eventItem.title} at ${eventItem.college} is now open.`,
      eventId: eventItem.id,
      type: 'new-event'
    });
    return liveEvent;
  }

  function rejectEvent(id, reason) {
    const pending = getPendingEvents();
    const eventItem = pending.find(event => event.id === id);
    if (eventItem) {
      const rejected = getRejectedEvents();
      const rejectedEvent = { ...eventItem, status: 'rejected', rejectedAt: new Date().toISOString(), rejectedReason: reason || 'No reason provided.' };
      rejected.push(rejectedEvent);
      write(keys.rejected, rejected);
      addNotification(eventItem.submittedBy || 'institution', {
        title: `${eventItem.title} was rejected`,
        message: `${eventItem.title} was rejected: ${rejectedEvent.rejectedReason}`,
        eventId: eventItem.id,
        type: 'rejection'
      });
    }
    write(keys.pending, pending.filter(event => event.id !== id));
  }

  function getEventById(id, options) {
    const pools = [getApprovedEvents()];
    if (options && options.includePending) pools.push(getPendingEvents(), getRejectedEvents());
    return pools.flat().find(eventItem => eventItem.id === id) || null;
  }

  function getExpiredEvents() {
    return getApprovedEvents().filter(eventItem => eventItem.status === 'expired');
  }

  function archiveEvent(id) {
    const archived = read(keys.archived, []);
    if (!archived.includes(id)) archived.push(id);
    write(keys.archived, archived);
    return true;
  }

  function restoreEvent(id) {
    write(keys.expired, read(keys.expired, []).filter(item => item !== id));
    write(keys.archived, read(keys.archived, []).filter(item => item !== id));
    const approved = read(keys.approved, []).map(eventItem => eventItem.id === id ? { ...eventItem, status: 'approved' } : eventItem);
    write(keys.approved, approved);
    return true;
  }

  function getSession() {
    return read(keys.session, null);
  }

  function setSession(session) {
    write(keys.session, { ...session, loggedInAt: new Date().toISOString() });
  }

  function clearSession() {
    localStorage.removeItem(keys.session);
    localStorage.removeItem('eventworld_token');
    sessionStorage.removeItem('eventworld_token');
  }

  function getRegisteredEvents() {
    return read(keys.registered, []);
  }

  function registerForEvent(eventId) {
    const registered = getRegisteredEvents();
    const eventItem = getEventById(eventId, { includePending: true });
    let registration = registered.find(item => item.eventId === eventId);
    if (!registration) {
      const session = getSession() || {};
      registration = {
        eventId,
        registrationId: `EW-${String(eventId || 'EVENT').slice(0, 6).toUpperCase()}-${registrationId()}`,
        registeredAt: new Date().toISOString(),
        studentName: session.name || session.email || 'Event World Student',
        studentEmail: session.email || '',
        college: session.college || 'College not set',
        teamName: session.teamName || 'Solo'
      };
      registered.push(registration);
      write(keys.registered, registered);
      localStorage.setItem(`ticket_${eventId}`, registration.registrationId);
      if (eventItem) {
        addNotification((getSession() && getSession().email) || 'student', {
          title: `Registration confirmed for ${eventItem.title}`,
          message: `Your ticket for ${eventItem.title} is ready.`,
          eventId,
          type: 'registration'
        });
        const totalSeats = Number(String(eventItem.seats || '').match(/\d+/)?.[0] || 0);
        if (totalSeats) {
          const remaining = Math.max(totalSeats - getRegisteredCount(eventId), 0);
          if (remaining <= Math.ceil(totalSeats * 0.1)) {
            addNotification('all', {
              title: `Only ${remaining} seats left for ${eventItem.title}!`,
              message: 'Share it with friends before registrations close.',
              eventId,
              type: 'seats'
            });
          }
        }
      }
    }
    return registration;
  }

  function cacheRegistration(eventId, data) {
    const registered = getRegisteredEvents();
    const session = getSession() || {};
    const registrationIdValue = data.registration_id || data.registrationId || `EW-${String(eventId || 'EVENT').slice(0, 6).toUpperCase()}-${registrationId()}`;
    const registration = {
      eventId,
      registrationId: registrationIdValue,
      registeredAt: data.registered_at || data.registeredAt || new Date().toISOString(),
      studentName: data.student_name || data.studentName || session.name || session.email || 'Event World Student',
      studentEmail: data.student_email || data.studentEmail || session.email || '',
      college: data.college || session.college || 'College not set',
      teamName: data.teamName || data.team_name || 'Solo'
    };
    const existingIndex = registered.findIndex(item => item.eventId === eventId);
    if (existingIndex >= 0) registered[existingIndex] = { ...registered[existingIndex], ...registration };
    else registered.push(registration);
    write(keys.registered, registered);
    localStorage.setItem(`ticket_${eventId}`, registration.registrationId);
    return registration;
  }

  function unregisterEvent(eventId) {
    const next = getRegisteredEvents().filter(item => item.eventId !== eventId);
    write(keys.registered, next);
    return next;
  }

  function getSavedEvents() {
    return read(keys.saved, []);
  }

  function toggleSavedEvent(eventId) {
    const saved = getSavedEvents();
    const next = saved.includes(eventId) ? saved.filter(id => id !== eventId) : [...saved, eventId];
    write(keys.saved, next);
    return next.includes(eventId);
  }

  function getEventsByType(type) {
    const normalizedType = String(type || '').toLowerCase();
    return getApprovedEvents().filter(eventItem => eventItem.type === normalizedType);
  }

  function searchEvents(query) {
    const q = String(query || '').trim().toLowerCase();
    if (!q) return getApprovedEvents();
    return getApprovedEvents().filter(eventItem => {
      const haystack = [
        eventItem.title,
        eventItem.college,
        eventItem.desc,
        eventItem.description,
        eventItem.type,
        eventItem.location,
        eventItem.tags.join(' ')
      ].join(' ').toLowerCase();
      return haystack.includes(q);
    });
  }

  function getUpcomingEvents(days) {
    const limit = Number(days || 7);
    const now = new Date();
    const end = new Date(now.getTime() + limit * 24 * 60 * 60 * 1000);
    return getApprovedEvents().filter(eventItem => {
      const eventDate = parseEventDate(eventItem.date);
      return eventDate && eventDate >= now && eventDate <= end;
    });
  }

  function getUserSubmissions() {
    const session = getSession();
    if (!session || !session.email) return [];
    const email = String(session.email).toLowerCase();
    return getSubmittedEvents().filter(eventItem => eventItem.submittedBy && String(eventItem.submittedBy).toLowerCase() === email);
  }

  function getRegisteredCount(eventId) {
    const base = Array.from(String(eventId || 'event')).reduce((sum, char) => sum + char.charCodeAt(0), 0);
    const seed = 40 + (base % 190);
    const localCount = getRegisteredEvents().filter(item => item.eventId === eventId).length;
    const eventItem = getEventById(eventId);
    const popularity = eventItem ? Number(eventItem.popularity || 0) : 0;
    return seed + localCount + popularity;
  }

  function getViewCount(eventId) {
    const views = read(keys.views, {});
    views[eventId] = Number(views[eventId] || 0) + 1;
    write(keys.views, views);
    return views[eventId];
  }

  function peekViewCount(eventId) {
    const views = read(keys.views, {});
    return Number(views[eventId] || 0);
  }

  function editEvent(id, updatedFields) {
    const session = getSession();
    if (!session || session.role !== 'institution') return null;
    const email = String(session.email || '').toLowerCase();
    const collections = [
      { key: keys.pending, status: 'pending' },
      { key: keys.approved, status: 'approved' }
    ];
    for (const collection of collections) {
      const list = read(collection.key, []).map(eventItem => normalizeEvent(eventItem, eventItem.status || collection.status));
      const index = list.findIndex(eventItem => eventItem.id === id && String(eventItem.submittedBy || '').toLowerCase() === email);
      if (index >= 0) {
        list[index] = normalizeEvent({ ...list[index], ...updatedFields, id, submittedBy: list[index].submittedBy }, list[index].status);
        write(collection.key, list);
        return list[index];
      }
    }
    return null;
  }

  function cleanExpiredEvents() {
    const now = new Date();
    const cutoff = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1, 23, 59, 59);
    const archivedIds = read(keys.archived, []);
    const expiredIds = read(keys.expired, []);
    let count = 0;
    const allApproved = getApprovedEvents().filter(eventItem => !archivedIds.includes(eventItem.id));
    allApproved.forEach(eventItem => {
      const end = parseEventDate(eventItem.endDate || eventItem.date);
      if (end && end < cutoff && eventItem.status !== 'expired' && !expiredIds.includes(eventItem.id)) {
        expiredIds.push(eventItem.id);
        count += 1;
        getRegisteredEvents().filter(reg => reg.eventId === eventItem.id).forEach(() => {
          addNotification('all', {
            title: `${eventItem.title} has ended`,
            message: 'Thanks for participating!',
            type: 'expiry',
            eventId: eventItem.id
          });
        });
      }
    });
    write(keys.expired, expiredIds);
    const approved = read(keys.approved, []).map(eventItem => expiredIds.includes(eventItem.id) ? { ...eventItem, status: 'expired' } : eventItem);
    write(keys.approved, approved);
    return count;
  }

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

  function currentUserId() {
    const session = getSession();
    return session && session.email ? String(session.email).toLowerCase() : 'guest';
  }

  function getNotifications() {
    const userId = currentUserId();
    return read(keys.notifications, []).filter(note => !note.userId || note.userId === userId || note.userId === 'all');
  }

  function addNotification(userId, input) {
    if (arguments.length === 1) {
      input = userId;
      userId = currentUserId();
    }
    const notification = {
      id: input.id || `note-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      userId: String(userId || currentUserId()).toLowerCase(),
      title: input.title || 'Event World update',
      message: input.message || '',
      eventId: input.eventId || '',
      type: input.type || 'info',
      read: Boolean(input.read),
      createdAt: input.createdAt || new Date().toISOString()
    };
    write(keys.notifications, [notification, ...read(keys.notifications, [])].slice(0, 80));
    return notification;
  }

  function markNotificationsRead() {
    const userId = currentUserId();
    write(keys.notifications, read(keys.notifications, []).map(item => (!item.userId || item.userId === userId || item.userId === 'all') ? { ...item, read: true } : item));
  }

  function markAllRead() {
    markNotificationsRead();
  }

  function getUnreadCount() {
    return getNotifications().filter(item => !item.read).length;
  }

  function setupGlobalUi() {
    if (document.getElementById('eventWorldGlobalUi')) return;
    const style = document.createElement('style');
    style.id = 'eventWorldGlobalUi';
    style.textContent = `
      html { scroll-behavior: smooth; }
      body { transition: opacity 200ms ease; }
      body.page-fade-out { opacity: 0; }
      .ew-cursor, .ew-cursor-ring {
        position: fixed;
        pointer-events: none;
        border-radius: 50%;
        z-index: 100000;
      }
      .ew-cursor {
        width: 12px;
        height: 12px;
        background: #00f0ff;
        box-shadow: 0 0 16px #00f0ff;
      }
      .ew-cursor-ring {
        width: 42px;
        height: 42px;
        border: 1px solid rgba(0,240,255,0.42);
        transition: left 120ms ease, top 120ms ease, transform 180ms ease;
      }
      .ew-bell {
        position: fixed;
        top: 18px;
        right: 18px;
        z-index: 10050;
        width: 42px;
        height: 42px;
        border-radius: 50%;
        border: 1px solid rgba(0,240,255,0.28);
        color: #00f0ff;
        background: rgba(8,13,20,0.9);
        box-shadow: 0 0 24px rgba(0,240,255,0.14);
        cursor: pointer;
      }
      .ew-bell-count {
        position: absolute;
        top: -6px;
        right: -6px;
        min-width: 20px;
        height: 20px;
        display: grid;
        place-items: center;
        border-radius: 50%;
        color: #000;
        background: #ff2d78;
        font: 800 11px Arial, sans-serif;
      }
      .ew-notes {
        position: fixed;
        top: 68px;
        right: 18px;
        width: min(360px, calc(100vw - 24px));
        max-height: 440px;
        overflow: auto;
        z-index: 10049;
        display: none;
        border: 1px solid rgba(0,240,255,0.2);
        border-radius: 12px;
        background: rgba(8,13,20,0.97);
        box-shadow: 0 24px 70px rgba(0,0,0,0.45);
      }
      .ew-notes.open { display: block; }
      .ew-notes-head {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 1rem;
        padding: 0.9rem 1rem;
        border-bottom: 1px solid rgba(0,240,255,0.14);
        color: #e0eeff;
        font: 800 13px 'Orbitron', monospace;
      }
      .ew-notes-head button {
        border: none;
        color: #00f0ff;
        background: transparent;
        cursor: pointer;
        font: 700 11px 'Space Mono', monospace;
      }
      .ew-note {
        padding: 0.85rem 1rem;
        border-bottom: 1px solid rgba(0,240,255,0.08);
        cursor: pointer;
      }
      .ew-note:hover { background: rgba(0,240,255,0.06); }
      .ew-note.unread { border-left: 3px solid #00f0ff; }
      .ew-note strong {
        display: block;
        color: #e0eeff;
        margin-bottom: 0.25rem;
      }
      .ew-note span {
        color: #6f87a3;
        font-size: 0.9rem;
      }
      .ew-menu-toggle {
        display: none;
        border: 1px solid rgba(0,240,255,0.24);
        color: #00f0ff;
        background: rgba(8,13,20,0.88);
        border-radius: 8px;
        padding: 0.45rem 0.65rem;
        cursor: pointer;
        font: 900 18px Arial, sans-serif;
      }
      @media (max-width: 760px), (pointer: coarse) {
        body { cursor: auto !important; }
        .ew-cursor, .ew-cursor-ring, .cursor, .cursor-ring { display: none !important; }
        .ew-bell { top: 10px; right: 10px; }
        .ew-menu-toggle { display: inline-flex; align-items: center; justify-content: center; }
        nav .nav-links, nav .links {
          display: none !important;
          position: absolute;
          top: 100%;
          right: 1rem;
          min-width: 210px;
          padding: 0.8rem;
          border: 1px solid rgba(0,240,255,0.18);
          border-radius: 12px;
          background: rgba(8,13,20,0.97);
          box-shadow: 0 20px 50px rgba(0,0,0,0.4);
          flex-direction: column;
          align-items: stretch;
        }
        nav .nav-links.open, nav .links.open { display: flex !important; }
        nav { position: relative; }
      }
    `;
    document.head.appendChild(style);

    if (!document.querySelector('.cursor') && !document.querySelector('.ew-cursor')) {
      const cursor = document.createElement('div');
      const ring = document.createElement('div');
      cursor.className = 'ew-cursor';
      ring.className = 'ew-cursor-ring';
      document.body.append(cursor, ring);
      document.addEventListener('mousemove', event => {
        cursor.style.left = `${event.clientX - 6}px`;
        cursor.style.top = `${event.clientY - 6}px`;
        ring.style.left = `${event.clientX - 21}px`;
        ring.style.top = `${event.clientY - 21}px`;
      });
    }

    if (document.querySelector('nav') && !document.querySelector('.ew-bell')) {
      const bell = document.createElement('button');
      bell.className = 'ew-bell';
      bell.type = 'button';
      bell.innerHTML = '🔔<span class="ew-bell-count">0</span>';
      const panel = document.createElement('div');
      panel.className = 'ew-notes';
      document.body.append(bell, panel);
      function renderNotes() {
        const notes = getNotifications();
        const unread = getUnreadCount();
        bell.querySelector('.ew-bell-count').textContent = unread;
        bell.querySelector('.ew-bell-count').style.display = unread ? 'grid' : 'none';
        panel.innerHTML = `
          <div class="ew-notes-head">
            <span>Notifications</span>
            <button type="button" id="ewMarkRead">Mark all read</button>
          </div>
          ${notes.length ? notes.map(note => `
            <div class="ew-note" data-event-id="${note.eventId}">
              <strong>${note.type === 'approval' ? '🎉' : note.type === 'rejection' ? '❌' : note.type === 'registration' ? '✅' : note.type === 'expiry' ? '⏰' : '🔔'} ${note.title}</strong>
              <span>${note.message} · ${timeAgo(note.createdAt)}</span>
            </div>
          `).join('') : '<div class="ew-note"><span>No notifications yet.</span></div>'}
        `;
        const mark = panel.querySelector('#ewMarkRead');
        if (mark) mark.onclick = () => { markAllRead(); renderNotes(); };
        panel.querySelectorAll('.ew-note[data-event-id]').forEach(item => {
          item.onclick = () => {
            const eventId = item.dataset.eventId;
            if (eventId) window.location.href = `event-detail.html?id=${encodeURIComponent(eventId)}`;
          };
        });
      }
      bell.onclick = () => {
        panel.classList.toggle('open');
        renderNotes();
      };
      renderNotes();
      window.EventWorldRefreshNotifications = renderNotes;
    }

    document.querySelectorAll('nav').forEach(nav => {
      const links = nav.querySelector('.nav-links, .links');
      if (!links || nav.querySelector('.ew-menu-toggle')) return;
      const toggle = document.createElement('button');
      toggle.type = 'button';
      toggle.className = 'ew-menu-toggle';
      toggle.textContent = '☰';
      toggle.onclick = () => links.classList.toggle('open');
      const container = nav.querySelector('.nav-inner') || nav;
      container.appendChild(toggle);
    });

    document.addEventListener('click', event => {
      const link = event.target.closest && event.target.closest('a[href]');
      if (!link) return;
      const href = link.getAttribute('href');
      if (!href || href.startsWith('#') || href.startsWith('mailto:') || href.startsWith('http')) return;
      if (link.target && link.target !== '_self') return;
      event.preventDefault();
      document.body.classList.add('page-fade-out');
      setTimeout(() => { window.location.href = href; }, 200);
    });
  }

  const localHosts = ['localhost', '127.0.0.1', ''];
  const API_BASE = window.EVENT_WORLD_API_BASE || (localHosts.includes(window.location.hostname) ? 'http://localhost:8000' : window.location.origin);
  const tokenKey = 'eventworld_token';

  function apiToken() {
    return localStorage.getItem(tokenKey) || sessionStorage.getItem(tokenKey) || '';
  }

  function saveApiToken(token, remember) {
    if (!token) return;
    const target = remember === false ? sessionStorage : localStorage;
    const other = remember === false ? localStorage : sessionStorage;
    target.setItem(tokenKey, token);
    other.removeItem(tokenKey);
  }

  function clearApiToken() {
    localStorage.removeItem(tokenKey);
    sessionStorage.removeItem(tokenKey);
  }

  function apiEventToLocal(eventItem) {
    if (!eventItem) return eventItem;
    return normalizeEvent({
      ...eventItem,
      id: eventItem.id || eventItem._id,
      submittedBy: eventItem.submittedBy || eventItem.submitted_by || '',
      submittedAt: eventItem.submittedAt || eventItem.submitted_at || '',
      approvedAt: eventItem.approvedAt || eventItem.approved_at || '',
      rejectedReason: eventItem.rejectedReason || eventItem.rejected_reason || '',
      posterUrl: eventItem.posterUrl || eventItem.poster_url || null,
      popularity: eventItem.popularity || eventItem.registration_count || eventItem.registrationCount || 0,
    }, eventItem.status || 'approved');
  }

  async function apiRequest(path, options) {
    const opts = options || {};
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 12000);
    const headers = {
      'Content-Type': 'application/json',
      ...(opts.headers || {})
    };
    const token = apiToken();
    if (token) headers.Authorization = `Bearer ${token}`;
    try {
      const response = await fetch(`${API_BASE}${path}`, {
        ...opts,
        headers,
        signal: controller.signal,
        body: opts.body && typeof opts.body !== 'string' ? JSON.stringify(opts.body) : opts.body
      });
      if (!response.ok) {
        let message = `API request failed (${response.status})`;
        try {
          const data = await response.json();
          message = data.detail || message;
        } catch (error) {}
        const requestError = new Error(message);
        requestError.status = response.status;
        throw requestError;
      }
      if (response.status === 204) return null;
      return response.json();
    } finally {
      clearTimeout(timeout);
    }
  }

  async function apiWithFallback(action, fallback) {
    try {
      EventWorldAPI.lastFallback = false;
      return await action();
    } catch (error) {
      EventWorldAPI.lastFallback = true;
      console.warn('[EventWorldAPI] Using local fallback:', error.message);
      return typeof fallback === 'function' ? fallback(error) : fallback;
    }
  }

  const EventWorldAPI = {
    API_BASE,
    tokenKey,
    lastFallback: false,
    getToken: apiToken,
    setToken: saveApiToken,
    clearToken: clearApiToken,
    async login(email, password, role, options) {
      const result = await apiRequest('/api/auth/login', { method: 'POST', body: { email, password, role } });
      saveApiToken(result.token, !options || options.remember !== false);
      setSession(result.user);
      localStorage.setItem('eventworld_last_email', email);
      return result;
    },
    async register(data, options) {
      const result = await apiRequest('/api/auth/register', { method: 'POST', body: data });
      saveApiToken(result.token, !options || options.remember !== false);
      setSession(result.user);
      localStorage.setItem('eventworld_last_email', data.email || '');
      return result;
    },
    async getMe() {
      return apiRequest('/api/auth/me');
    },
    async isLoggedIn() {
      if (!apiToken() && !getSession()) return false;
      try {
        const user = await this.getMe();
        if (!user) {
          clearApiToken();
          clearSession();
          return false;
        }
        setSession(user);
        return true;
      } catch (error) {
        clearApiToken();
        clearSession();
        return false;
      }
    },
    async logout() {
      await apiWithFallback(() => apiRequest('/api/auth/logout', { method: 'POST' }), { ok: true });
      clearApiToken();
      clearSession();
      return { ok: true };
    },
    async getEvents(filters) {
      const params = new URLSearchParams();
      Object.entries(filters || {}).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== '') params.set(key, value);
      });
      const query = params.toString() ? `?${params.toString()}` : '';
      return apiWithFallback(
        async () => (await apiRequest(`/api/events${query}`)).map(apiEventToLocal),
        () => getApprovedEvents().filter(eventItem => eventItem.status !== 'expired')
      );
    },
    async getEventById(id) {
      return apiWithFallback(
        async () => apiEventToLocal(await apiRequest(`/api/events/${encodeURIComponent(id)}`)),
        () => getEventById(id, { includePending: true })
      );
    },
    async submitEvent(data) {
      return apiWithFallback(
        async () => apiEventToLocal(await apiRequest('/api/events/submit', { method: 'POST', body: data })),
        () => submitEvent(data)
      );
    },
    async updateEvent(id, data) {
      return apiWithFallback(
        async () => apiEventToLocal(await apiRequest(`/api/events/${encodeURIComponent(id)}`, { method: 'PUT', body: data })),
        () => editEvent(id, data)
      );
    },
    async registerForEvent(id) {
      return apiWithFallback(
        async () => {
          const result = await apiRequest(`/api/events/${encodeURIComponent(id)}/register`, { method: 'POST' });
          cacheRegistration(id, result);
          return result;
        },
        () => registerForEvent(id)
      );
    },
    async verifyTicket(registrationId) {
      return apiRequest(`/api/tickets/verify/${encodeURIComponent(registrationId)}`);
    },
    async toggleSave(id) {
      return apiWithFallback(
        async () => {
          const result = await apiRequest(`/api/events/${encodeURIComponent(id)}/save`, { method: 'POST' });
          if (Boolean(result.saved) !== getSavedEvents().includes(id)) toggleSavedEvent(id);
          return result;
        },
        () => ({ saved: toggleSavedEvent(id) })
      );
    },
    async getRegisteredEvents() {
      return apiWithFallback(
        async () => (await apiRequest('/api/events/registered')).map(apiEventToLocal),
        () => {
          const ids = getRegisteredEvents().map(item => item.eventId);
          return getApprovedEvents().filter(eventItem => ids.includes(eventItem.id));
        }
      );
    },
    async getSavedEvents() {
      return apiWithFallback(
        async () => (await apiRequest('/api/events/saved')).map(apiEventToLocal),
        () => {
          const ids = getSavedEvents();
          return getApprovedEvents().filter(eventItem => ids.includes(eventItem.id));
        }
      );
    },
    async getNotifications() {
      return apiWithFallback(
        async () => (await apiRequest('/api/notifications')).map(note => ({
          ...note,
          eventId: note.eventId || note.event_id || '',
          read: Boolean(note.read || note.is_read),
          createdAt: note.createdAt || note.created_at
        })),
        () => getNotifications()
      );
    },
    async markRead(id) {
      return apiWithFallback(
        () => apiRequest(`/api/notifications/read/${encodeURIComponent(id)}`, { method: 'POST' }),
        { ok: true }
      );
    },
    async markAllRead() {
      return apiWithFallback(
        () => apiRequest('/api/notifications/read-all', { method: 'POST' }),
        () => {
          markAllRead();
          return { ok: true };
        }
      );
    },
    async adminGetPending() {
      return apiWithFallback(
        async () => (await apiRequest('/api/admin/pending')).map(apiEventToLocal),
        () => getPendingEvents()
      );
    },
    async adminGetEvents() {
      return apiWithFallback(
        async () => (await apiRequest('/api/admin/events')).map(apiEventToLocal),
        () => [...getPendingEvents(), ...getApprovedEvents(), ...getRejectedEvents()]
      );
    },
    async adminStats() {
      return apiWithFallback(
        () => apiRequest('/api/admin/stats'),
        () => ({
          total_users: 0,
          total_students: 0,
          total_institutions: 0,
          total_events: getApprovedEvents().length + getPendingEvents().length + getRejectedEvents().length,
          pending_count: getPendingEvents().length,
          approved_count: getApprovedEvents().length,
          rejected_count: getRejectedEvents().length,
          total_registrations: getRegisteredEvents().length,
          new_users_today: 0
        })
      );
    },
    async adminApprove(id) {
      return apiWithFallback(
        async () => apiEventToLocal(await apiRequest(`/api/admin/approve/${encodeURIComponent(id)}`, { method: 'POST' })),
        () => approveEvent(id)
      );
    },
    async adminReject(id, reason) {
      return apiWithFallback(
        async () => apiEventToLocal(await apiRequest(`/api/admin/reject/${encodeURIComponent(id)}`, { method: 'POST', body: { reason } })),
        () => rejectEvent(id, reason)
      );
    }
  };

  window.EventWorldAPI = EventWorldAPI;

  window.EventWorldStore = {
    keys,
    typeMeta,
    normalizeEvent,
    getApprovedEvents,
    getPendingEvents,
    getRejectedEvents,
    getSubmittedEvents,
    submitEvent,
    approveEvent,
    rejectEvent,
    archiveEvent,
    restoreEvent,
    getEventById,
    getExpiredEvents,
    getSession,
    setSession,
    clearSession,
    getRegisteredEvents,
    registerForEvent,
    cacheRegistration,
    unregisterEvent,
    getSavedEvents,
    toggleSavedEvent,
    getEventsByType,
    searchEvents,
    getUpcomingEvents,
    getUserSubmissions,
    getRegisteredCount,
    getViewCount,
    peekViewCount,
    editEvent,
    getNotifications,
    addNotification,
    markNotificationsRead,
    markAllRead,
    getUnreadCount,
    cleanExpiredEvents,
    parseEventDate,
    prizeNumber,
    setupGlobalUi
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      purgeLegacySeedEvents();
      cleanExpiredEvents();
      setupGlobalUi();
    });
  } else {
    purgeLegacySeedEvents();
    cleanExpiredEvents();
    setupGlobalUi();
  }
})();
