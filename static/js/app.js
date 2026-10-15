/* app.js — Enciclopédia das Ervas Sagradas (Flask edition) */
'use strict';

// ── Constantes ────────────────────────────────────────────────
const ORIXA_COLORS = {
  "Oxalá":"#f5f5dc","Iemanjá":"#0077b6","Oxum":"#d4a017",
  "Ogum":"#3a7c3a","Xangô":"#ff6600","Iansã":"#c41e3a",
  "Oxóssi":"#4a7c59","Omolu":"#7a3b10","Exu":"#ff4400","Nanã":"#6a0dad"
};

const RITUALS = {
  banho: [
    { name:'Banho de Proteção e Limpeza',
      purpose:'Limpa energias densas e cria uma barreira protetora antes de rituais.',
      items:['Arruda','Alecrim','Guiné','Louro'],
      schedule:'Sexta-feira à noite',
      timing:'Use antes de iniciar trabalhos espirituais ou limpar a casa.',
      instructions:'Esta ficha apenas registra uma associação cultural; não descreve preparo nem recomenda aplicação, ingestão ou inalação.' },
    { name:'Banho de Amor e Abertura de Coração',
      purpose:'Atrai amor, afasta mágoas e fortalece vínculos afetivos.',
      items:['Rosa Vermelha','Manjericão','Canela','Camomila'],
      schedule:'Segunda-feira pela manhã',
      timing:'Ideal para iniciar uma nova fase amorosa ou fortalecer relações.',
      instructions:'Esta ficha apenas registra uma associação cultural; não descreve preparo nem recomenda aplicação, ingestão ou inalação.' },
    { name:'Banho de Calma e Purificação',
      purpose:'Associação simbólica de tranquilidade em algumas práticas culturais; não é indicação de tratamento.',
      items:['Lavanda','Camomila','Erva-Cidreira','Jasmim'],
      schedule:'Quarta-feira ao entardecer',
      timing:'Horário simbólico registrado; não é orientação de saúde.',
      instructions:'Esta ficha apenas registra uma associação cultural; não descreve preparo nem recomenda aplicação, ingestão ou inalação.' },
    { name:'Pesquisa visual: plantas e água', purpose:'Atividade educativa de comparação entre partes botânicas por fotografias, sem preparo corporal.', items:['Alecrim','Rosa Branca','Lavanda'], schedule:'Sem calendário específico', timing:'Proposta documental.', instructions:'Compare imagens, nomes e fontes. Registre dúvidas de identificação. Não prepare nem aplique plantas.' },
  ],
  chas: [
    { name:'Registro simbólico: clareza e proteção',
      purpose:'Exemplo de associação simbólica em práticas tradicionais; não é uma recomendação de consumo.',
      items:['Alecrim','Hortelã','Canela'],
      schedule:'Terça-feira pela manhã',
      timing:'Use antes de estudar, trabalhar ou fazer decisões importantes.',
      instructions:'Esta ficha apenas registra uma associação cultural; não descreve preparo nem recomenda aplicação, ingestão ou inalação.' },
    { name:'Registro simbólico: sono tranquilo',
      purpose:'Exemplo de associação simbólica em práticas tradicionais; não é uma recomendação de consumo.',
      items:['Camomila','Lavanda','Erva-Cidreira'],
      schedule:'Noite de sexta-feira',
      timing:'Horário simbólico registrado; não é orientação de consumo.',
      instructions:'Esta ficha apenas registra uma associação cultural; não descreve preparo nem recomenda aplicação, ingestão ou inalação.' },
    { name:'Registro simbólico: prosperidade e boa sorte',
      purpose:'Exemplo de associação simbólica em práticas tradicionais; não é uma recomendação de consumo.',
      items:['Canela','Erva-Doce','Manjericão'],
      schedule:'Quinta-feira pela manhã',
      timing:'Horário simbólico registrado; não é orientação de consumo.',
      instructions:'Esta ficha apenas registra uma associação cultural; não descreve preparo nem recomenda aplicação, ingestão ou inalação.' },
    { name:'Caderno de referências sobre chás', purpose:'Atividade de pesquisa de nomes botânicos, partes vegetais e fontes publicadas; não recomenda consumo.', items:['Camomila','Hortelã','Erva-Cidreira'], schedule:'Sem calendário específico', timing:'Atividade de leitura e anotação.', instructions:'Registre espécie, parte da planta e referência. Não prepare nem consuma infusões com base nesta atividade.' },
    { name:'Chá de camomila', traditionalUse:'Associada a momentos de pausa, acolhimento e serenidade em práticas domésticas e culturais.', benefits:'Benefício simbólico proposto: criar um momento de calma e cuidado pessoal.', source:'https://powo.science.kew.org/taxon/urn:lsid:ipni.org:names:154715-2', items:['Camomila'], schedule:'Sem calendário específico', timing:'Ficha cultural; não indica horário de consumo.', instructions:'Registro cultural e simbólico. Esta ficha não apresenta receita nem recomenda ingestão.' },
    { name:'Chá de erva-cidreira', traditionalUse:'Associada simbolicamente a tranquilidade, harmonia e acolhimento.', benefits:'Benefício simbólico proposto: representar descanso e equilíbrio no cotidiano.', source:'https://powo.science.kew.org/taxon/450084-1', items:['Erva-Cidreira'], schedule:'Sem calendário específico', timing:'Ficha cultural; não indica horário de consumo.', instructions:'Registro cultural e simbólico. Esta ficha não apresenta receita nem recomenda ingestão.' },
    { name:'Chá de hortelã', traditionalUse:'Associada a frescor, renovação e clareza em algumas representações culturais.', benefits:'Benefício simbólico proposto: evocar leveza e renovação.', source:'https://powo.science.kew.org/taxon/urn:lsid:ipni.org:names:451162-1', items:['Hortelã'], schedule:'Sem calendário específico', timing:'Ficha cultural; não indica horário de consumo.', instructions:'Registro cultural e simbólico. Esta ficha não apresenta receita nem recomenda ingestão.' },
    { name:'Chá de alecrim', traditionalUse:'Associado simbolicamente a clareza, proteção e lembrança em diferentes tradições.', benefits:'Benefício simbólico proposto: representar foco, memória e renovação.', source:'https://powo.science.kew.org/taxon/457138-1', items:['Alecrim'], schedule:'Sem calendário específico', timing:'Ficha cultural; não indica horário de consumo.', instructions:'Registro cultural e simbólico. Esta ficha não apresenta receita nem recomenda ingestão.' }

  ],
  defumacao: [
    { name:'Defumação de Limpeza Profunda',
      purpose:'Renova a energia do ambiente e elimina vibrações negativas.',
      items:['Guiné','Arruda','Alecrim','Incenso (Olíbano)'],
      schedule:'Sábado de manhã',
      timing:'Use antes de iniciar trabalhos espirituais ou após discussões intensas.',
      instructions:'Esta ficha apenas registra uma associação cultural; não descreve preparo nem recomenda aplicação, ingestão ou inalação.' },
    { name:'Defumação de Prosperidade',
      purpose:'Aumenta a atração de abundância e afasta bloqueios financeiros.',
      items:['Canela','Cravo','Manjericão','Mirra'],
      schedule:'Sexta-feira à tarde',
      timing:'Ideal antes de fazer contas ou pedidos de prosperidade.',
      instructions:'Esta ficha apenas registra uma associação cultural; não descreve preparo nem recomenda aplicação, ingestão ou inalação.' },
    { name:'Defumação de Paz e Harmonia',
      purpose:'Suaviza tensões e traz serenidade ao lar.',
      items:['Jasmim','Lavanda','Benjoim-de-Cheiro'],
      schedule:'Domingo ao entardecer',
      timing:'Use depois de um dia cansativo.',
      instructions:'Esta ficha apenas registra uma associação cultural; não descreve preparo nem recomenda aplicação, ingestão ou inalação.' },
    { name:'Pesquisa de resinas e aromas', purpose:'Atividade de identificação de resinas e materiais aromáticos por imagens e fontes documentais.', items:['Olíbano','Mirra','Benjoim-de-Cheiro'], schedule:'Sem calendário específico', timing:'Proposta educativa sem queima de materiais.', instructions:'Pesquise nomes, origem e formas comerciais em fontes confiáveis. Não queime nem inale fumaça ou vapores.' },
  ],
  simbolicos: [
    { name:'Caderno das estações',
      purpose:'Exercício editorial de observação e registro, sem vínculo com uma tradição religiosa específica.',
      items:['Cúrcuma-da-Terra','Casca de Laranja','Casca de Limão'],
      schedule:'Sem calendário específico',
      timing:'Pode ser feito como atividade de escrita e memória botânica.',
      instructions:'Use fotografias ou escreva apenas os nomes dos itens. Registre cores, lembranças e perguntas. Não é necessário preparar, consumir, queimar ou aplicar plantas.' },
    { name:'Mesa de objetos botânicos',
      purpose:'Atividade de observação sobre a diferença entre plantas e produtos florais.',
      items:['Água de Rosas','Água de Flor de Laranjeira','Hidrolato de Lavanda'],
      schedule:'Sem calendário específico',
      timing:'Proposta educativa; não representa uma prática religiosa tradicional.',
      instructions:'Observe os rótulos ou use imagens do catálogo. Se usar embalagens, mantenha-as fechadas e fora do alcance de crianças e animais. Não ingerir, inalar ou aplicar os produtos.' },
    { name:'Roda de cores e lembranças',
      purpose:'Exercício contemplativo autoral para organizar memórias e associações pessoais.',
      items:['Alecrim','Rosa Branca','Lavanda','Cúrcuma-da-Terra'],
      schedule:'Sem calendário específico',
      timing:'Atividade opcional, sem promessa de resultado ou efeito terapêutico.',
      instructions:'Escolha imagens dos itens, associe cada cor a uma lembrança e anote o que deseja guardar ou pesquisar. Não requer contato, preparo, ingestão ou queima de materiais.' }
  ]
};

// ── Estado ─────────────────────────────────────────────────────
let activeTab        = 'ervas';
let selectedHerbIds  = new Set();
let lastFocusedCard  = null;
let fetchTimer       = null;
let loadedHerbs      = [];

// ── Init ───────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  setupTabs();
  setupFilters();
  setupModal();
  setupCompare();
  applyFilters();
});

// ── Tabs ───────────────────────────────────────────────────────
function setupTabs() {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => {
        b.classList.remove('active');
        b.setAttribute('aria-selected', 'false');
      });
      btn.classList.add('active');
      btn.setAttribute('aria-selected', 'true');
      activeTab = btn.dataset.tab;
      selectedHerbIds.clear();
      applyFilters();
    });
  });
}

// ── Filtros ────────────────────────────────────────────────────
function setupFilters() {
  ['search','filter-temp','filter-elem','filter-cat'].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener('input',  debounceFilter);
    el.addEventListener('change', debounceFilter);
  });
}

function debounceFilter() {
  clearTimeout(fetchTimer);
  fetchTimer = setTimeout(applyFilters, 250);
}

function applyFilters() {
  const filterSection = document.getElementById('filter-section');
  const comparePanel  = document.getElementById('compare-panel');
  const herbGrid      = document.getElementById('herb-grid');
  const ritualGrid    = document.getElementById('ritual-grid');

  // Abas de rituais
  if (['banho','chas','defumacao','rituais'].includes(activeTab) && activeTab !== 'banho') {
    // "rituais" mostra todos os 3 grupos
  }

  const isHerbTab    = activeTab === 'ervas';
  const isRitualOnly = ['rituais'].includes(activeTab);
  const isSubRitual  = ['banho','chas','defumacao'].includes(activeTab);

  if (filterSection) filterSection.style.display = isHerbTab ? '' : 'none';
  if (comparePanel)  comparePanel.classList.toggle('hidden', !isHerbTab);
  if (herbGrid)      herbGrid.classList.toggle('hidden', !isHerbTab);
  if (ritualGrid)    ritualGrid.classList.toggle('hidden', isHerbTab);

  if (isHerbTab) {
    fetchHerbs();
  } else if (isRitualOnly) {
    renderAllRituals();
  } else if (isSubRitual) {
    renderRituals(activeTab);
  }
}

// ── Fetch ervas via API ────────────────────────────────────────
function fetchHerbs() {
  const q    = document.getElementById('search')?.value.trim()      || '';
  const temp = document.getElementById('filter-temp')?.value        || '';
  const elem = document.getElementById('filter-elem')?.value        || '';
  const cat  = document.getElementById('filter-cat')?.value         || '';

  const params = new URLSearchParams({ tab:'ervas', q, temp, elem, cat });

  fetch('/api/ervas?' + params)
    .then(r => r.json())
    .then(herbs => {
      loadedHerbs = herbs;
      document.getElementById('showing-count').textContent = herbs.length;
      renderHerbs(herbs);
    })
    .catch(() => {
      const grid = document.getElementById('herb-grid');
      if (grid) grid.innerHTML = '<div class="no-results">Erro ao carregar itens. Tente recarregar a página.</div>';
    });
}

// ── Renderizar cards ────────────────────────────────────────────
function renderHerbs(herbs) {
  const grid = document.getElementById('herb-grid');
  if (!grid) return;

  if (!herbs.length) {
    grid.innerHTML = '<div class="no-results">Nenhum item encontrado. Tente outros filtros ou termos.</div>';
    updateComparePanel([]);
    return;
  }

  grid.innerHTML = herbs.map(herbCardHTML).join('');

  grid.querySelectorAll('.herb-card').forEach(card => {
    const id = Number(card.dataset.id);

    const cb = card.querySelector('.card-select input');
    if (cb) cb.addEventListener('change', () => toggleHerbSelection(id, herbs));

    card.addEventListener('click', e => {
      if (e.target.closest('.card-select, .image-credit')) return;
      openModal(id);
    });
    card.addEventListener('keydown', e => {
      if ((e.key === 'Enter' || e.key === ' ') && !e.target.closest('.card-select')) {
        e.preventDefault();
        openModal(id);
      }
    });
  });

  updateComparePanel(herbs);
}

function herbCardHTML(h) {
  const tempLabel = {quente:'🔥 Quente',fria:'💧 Fria',morna:'🌡️ Morna',neutra:'🌬️ Neutra'}[h.temp] || '';
  const sourceUrl = commonsFilePageUrl(h.img_url);
  const imgHtml = h.img_url
    ? `<img src="${escHtml(h.img_url)}" alt="${escHtml(h.name)} — ${escHtml(h.sci||'')}" loading="lazy" decoding="async"
            onerror="handleImageError(this)">`
    : `<div class="card-placeholder"><div class="placeholder-emoji">${escHtml(h.emoji)}</div></div>`;
  const creditHtml = sourceUrl ? `<a class="image-credit" href="${escHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer" aria-label="Ver autoria e licença da imagem no Wikimedia Commons">Foto · Wikimedia Commons ↗</a>` : '';

  const bathTags = (h.bath_uses||[]).slice(0,2).map(u => `<span class="tag">${escHtml(u)}</span>`).join('');
  const teaTag   = h.tea_uses?.length  ? '<span class="tag cha">Chá</span>'          : '';
  const fumTag   = h.can_fumigate      ? '<span class="tag fumigar">Defumação</span>' : '';
  const orixas   = (h.orixas||[]).map(o =>
    `<span class="orixa-dot" style="background:${ORIXA_COLORS[o]||'#5a8a68'}" title="${escHtml(o)}"></span>`
  ).join('');
  const sel     = selectedHerbIds.has(h.id) ? ' selected' : '';
  const selCtrl = `<label class="card-select">
    <input type="checkbox" ${selectedHerbIds.has(h.id)?'checked':''} aria-label="Selecionar ${escHtml(h.name)} para comparar">
    <span>Selecionar</span>
  </label>`;

  return `<article class="herb-card${sel}" data-id="${h.id}" role="button" tabindex="0"
                   aria-label="Abrir detalhes de ${escHtml(h.name)}">
    <div class="card-media">
      ${imgHtml}
      ${creditHtml}
      <span class="temp-badge temp-${h.temp}">${tempLabel}</span>
    </div>
    <div class="card-body">
      <div class="card-name">${escHtml(h.name)}</div>
      ${h.sci ? `<div class="card-sci">${escHtml(h.sci)}</div>` : ''}
      <div class="card-desc">${escHtml(h.desc||'')}</div>
      <div class="card-tags">${bathTags}${teaTag}${fumTag}</div>
      ${selCtrl}
    </div>
    <div class="card-footer">
      <div class="orixas-list">
        ${orixas}
        <span class="orixas-text">${escHtml((h.orixas||[]).join(', '))}</span>
      </div>
      <span class="tag badge-cat">${escHtml(categoryLabel(h.cat))}</span>
    </div>
  </article>`;
}

// ── Seleção e comparação ────────────────────────────────────────
function toggleHerbSelection(id, herbs) {
  if (selectedHerbIds.has(id)) {
    selectedHerbIds.delete(id);
  } else {
    if (selectedHerbIds.size >= 3) return;
    selectedHerbIds.add(id);
  }
  renderHerbs(herbs);
}

function setupCompare() {
  const btn = document.getElementById('compare-button');
  if (btn) btn.addEventListener('click', compareSelectedItems);
}

function updateComparePanel(herbs) {
  const container = document.getElementById('compare-selected-items');
  const btn       = document.getElementById('compare-button');
  const selected  = [...selectedHerbIds].map(id => herbs.find(h => h.id === id)).filter(Boolean);

  if (container) {
    container.innerHTML = selected.length
      ? selected.map(h => `<span class="compare-chip">✅ ${escHtml(h.name)}</span>`).join('')
      : '<span class="compare-placeholder">Selecione até 3 itens na aba Todas para comparar.</span>';
  }
  if (btn) btn.disabled = selected.length < 2;
}

function compareSelectedItems() {
  const ids    = [...selectedHerbIds];
  const result = document.getElementById('compare-result');
  if (!result || ids.length < 2) return;

  result.innerHTML = '<p style="color:var(--muted);font-size:.85rem">Analisando compatibilidade…</p>';

  fetch('/api/comparar', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ids})
  })
  .then(r => r.json())
  .then(data => {
    if (data.error) { result.innerHTML = `<p>${escHtml(data.error)}</p>`; return; }

    const cards = data.herbs.map(h => `
      <article class="compare-card">
        <div class="compare-card-header">
          ${h.img_url ? `<img class="compare-thumb" src="${escHtml(h.img_url)}" alt="Foto de ${escHtml(h.name)}" loading="lazy" onerror="handleImageError(this)">` : `<span class="compare-thumb-fallback">${escHtml(h.emoji||'🌿')}</span>`}
          <div>
            <strong>${escHtml(h.name)}</strong>
            <small>${escHtml(h.sci||'')}</small>
          </div>
        </div>
        <div class="compare-card-meta">
          <span class="tag badge-elem-${h.elem}">${escHtml(h.elem||'')}</span>
          <span class="tag temp-badge temp-${h.temp}" style="position:static">${escHtml(h.temp||'')}</span>
          <span class="tag badge-cat">${escHtml(categoryLabel(h.cat))}</span>
        </div>
        <p>${escHtml(h.desc||'Sem descrição.')}</p>
        <div class="compare-card-details">
          <span>Banho: ${escHtml((h.bath_uses||[]).join(', ')||'—')}</span>
          <span>Chá: ${escHtml((h.tea_uses||[]).join(', ')||'—')}</span>
          <span>Orixás: ${escHtml((h.orixas||[]).join(', ')||'—')}</span>
        </div>
      </article>`
    ).join('');

    const pairs = data.pairs.map(p => `
      <div class="recommend-card">
        <strong>${escHtml(p.a)} × ${escHtml(p.b)}</strong>
        <p>${escHtml(p.reason)}</p>
      </div>`
    ).join('');

    result.innerHTML = `
      <div class="compare-summary">${cards}</div>
      <div class="compare-reasons">${pairs}</div>`;
  })
  .catch(() => {
    result.innerHTML = '<p style="color:#f87171">Erro ao comparar itens.</p>';
  });
}

// ── Rituais ─────────────────────────────────────────────────────
function renderRituals(type) {
  const grid = document.getElementById('ritual-grid');
  if (!grid) return;
  const list = RITUALS[type] || [];
  if (!list.length) {
    grid.innerHTML = '<div class="no-results">Nenhum ritual para esta categoria.</div>';
    return;
  }
  const label = {banho:'Registro de banho',chas:'Associa\u00e7\u00e3o tradicional com ch\u00e1',defumacao:'Registro de defuma\u00e7\u00e3o'}[type] || type;
  grid.innerHTML = list.map(r => `
    <article class="ritual-card">
      <div class="ritual-card-header">
        <strong>${escHtml(r.name)}</strong>
        <span class="tag badge-cat">${label}</span>
      </div>
      ${r.purpose ? `<p class="ritual-purpose">${escHtml(r.purpose)}</p>` : ''}
      ${teaDetailsHTML(r)}
      <div class="ritual-meta">
        <div class="ritual-item-list"><strong>Itens:</strong>${ritualItemsHTML(r.items)}</div>
        <span><strong>Melhor dia:</strong> ${escHtml(r.schedule)}</span>
        <span><strong>Quando usar:</strong> ${escHtml(r.timing)}</span>
      </div>
      <div class="ritual-instructions">
        <strong>Como fazer:</strong>
        <p>${escHtml(r.instructions)}</p>
      </div>
    </article>`).join('');
}


function teaDetailsHTML(ritual) {
  if (!ritual.traditionalUse && !ritual.benefits) return '';
  return `<div class="ritual-tea-details">
    ${ritual.traditionalUse ? `<p><strong>Utilidade tradicional:</strong> ${escHtml(ritual.traditionalUse)}</p>` : ''}
    ${ritual.benefits ? `<p><strong>Benefício simbólico:</strong> ${escHtml(ritual.benefits)}</p>` : ''}
    ${ritual.source ? `<a href="${escHtml(ritual.source)}" target="_blank" rel="noopener noreferrer">Ver identificação botânica no Kew ↗</a>` : ''}
  </div>`;
}

function renderAllRituals() {
  const grid = document.getElementById('ritual-grid');
  if (!grid) return;
  const sections = [
    ['banho',     '🚿 Associações com banhos'],
    ['chas',      '\uD83C\uDF75 Ch\u00e1s e associa\u00e7\u00f5es tradicionais'],
    ['defumacao', '🔥 Associações com defumação'],
    ['simbolicos','📝 Práticas simbólicas e educativas'],
  ];
  grid.innerHTML = sections.map(([type, title]) => {
    const list = RITUALS[type] || [];
    const cards = list.map(r => `
      <article class="ritual-card">
        <div class="ritual-card-header">
          <strong>${escHtml(r.name)}</strong>
          <span class="tag badge-cat">${title.split(' ').slice(1).join(' ')}</span>
        </div>
        ${r.purpose ? `<p class="ritual-purpose">${escHtml(r.purpose)}</p>` : ''}
        ${teaDetailsHTML(r)}
        <div class="ritual-meta">
          <div class="ritual-item-list"><strong>Itens:</strong>${ritualItemsHTML(r.items)}</div>
          <span><strong>Melhor dia:</strong> ${escHtml(r.schedule)}</span>
        </div>
        <div class="ritual-instructions"><strong>Como fazer:</strong><p>${escHtml(r.instructions)}</p></div>
      </article>`).join('');
    return `<h3 style="color:var(--accent);font-size:1rem;padding:.4rem 0">${title}</h3>${cards}`;
  }).join('');
}

// ── Modal ───────────────────────────────────────────────────────
function setupModal() {
  document.getElementById('modal-overlay')?.addEventListener('click', e => {
    if (e.target.id === 'modal-overlay') closeModal();
  });
  document.getElementById('modal-close-btn')?.addEventListener('click', closeModal);
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
}

function openModal(id) {
  fetch(`/api/ervas/${id}`)
    .then(r => r.json())
    .then(h => renderModal(h))
    .catch(() => {});
}

function renderModal(h) {
  // Imagem
  const imgWrap = document.getElementById('modal-image');
  const sourceUrl = commonsFilePageUrl(h.img_url);
  imgWrap.innerHTML = h.img_url
    ? `<img src="${escHtml(h.img_url)}" alt="${escHtml(h.name)} — ${escHtml(h.sci||'')}" decoding="async"
            onerror="handleImageError(this)">
       ${sourceUrl ? `<a class="image-credit" href="${escHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">Foto e licença · Wikimedia Commons ↗</a>` : ''}`
    : `<div class="modal-emoji">${escHtml(h.emoji||'🌿')}</div>`;
  imgWrap.innerHTML += `<div class="modal-temp-bar"
    style="position:absolute;bottom:0;left:0;right:0;height:4px;
           background:linear-gradient(90deg,${tempColor(h.temp)},transparent)"></div>`;

  document.getElementById('modal-name').textContent = h.name || '';
  document.getElementById('modal-sci').textContent  = h.sci  || '';

  // Badges
  const elemClass = {'fogo':'badge-elem-fogo','água':'badge-elem-água','terra':'badge-elem-terra','ar':'badge-elem-ar'}[h.elem]||'badge-cat';
  document.getElementById('modal-badges').innerHTML = [
    `<span class="modal-badge ${elemClass}">${escHtml(h.elem||'')}</span>`,
    `<span class="modal-badge badge-cat">${escHtml(categoryLabel(h.cat))}</span>`,
    `<span class="modal-badge badge-temp">${escHtml(h.temp||'')}</span>`,
  ].join('');

  // Seções
  let sec = '';
  if (h.desc)             sec += sectionHTML('Descrição cultural', h.desc);
  if (h.spiritual)        sec += sectionHTML('Associações espirituais', h.spiritual);
  if (h.bath_uses?.length) sec += listSection('🚿 Usos em Banho', h.bath_uses, 'use-chip');
  if (h.tea_uses?.length)  sec += listSection('🍵 Usos internos relatados (não avaliados)', h.tea_uses, 'use-chip');
  if (h.can_fumigate && h.fumig) sec += sectionHTML('🔥 Defumação', h.fumig);
  if (h.orixas?.length)   sec += badgeSection('🌟 Orixás', h.orixas.map(o => ({label:o, color:ORIXA_COLORS[o]||'#5a8a68'})));
  if (h.compat?.length || h.incompat?.length) sec += compatSection(h.compat, h.incompat);
  if (h.preparo)          sec += sectionHTML('📝 Preparo', h.preparo);
  sec += sectionHTML('Contraindicações e limites', h.contraindications || 'Não avaliados individualmente; não presumir segurança para ingestão ou uso tópico.');
  sec += sectionHTML('Fontes específicas', h.medical_sources || 'Sem referência específica revisada para esta espécie.');

  document.getElementById('modal-sections').innerHTML = sec;

  const overlay = document.getElementById('modal-overlay');
  overlay.classList.add('open');
  overlay.setAttribute('aria-hidden', 'false');
  document.body.style.overflow = 'hidden';
  lastFocusedCard = document.activeElement;
  document.getElementById('modal-close-btn')?.focus();
}

function closeModal() {
  const overlay = document.getElementById('modal-overlay');
  if (!overlay) return;
  overlay.classList.remove('open');
  overlay.setAttribute('aria-hidden', 'true');
  document.body.style.overflow = '';
  lastFocusedCard?.focus();
  lastFocusedCard = null;
}

// ── Helpers de renderização ─────────────────────────────────────
function tempColor(t) {
  return {quente:'#e05c2a',fria:'#4a9aba',morna:'#d4882a',neutra:'#7a9e7e'}[t]||'#5a8a68';
}
function categoryLabel(category) {
  return ({liquido:'Líquido / hidrolato'})[category] || category || '';
}
function sectionHTML(title, text) {
  return `<div class="modal-section"><h3>${title}</h3><p>${escHtml(text)}</p></div>`;
}
function listSection(title, items, cls) {
  return `<div class="modal-section"><h3>${title}</h3><div class="uses-list">
    ${items.map(i=>`<span class="${cls}">${escHtml(i)}</span>`).join('')}
  </div></div>`;
}
function badgeSection(title, items) {
  return `<div class="modal-section"><h3>${title}</h3><div class="orixa-chips">
    ${items.map(i=>`<span class="orixa-chip"
      style="background:${i.color}33;border:1px solid ${i.color}55;color:${i.color}"
    >${escHtml(i.label)}</span>`).join('')}
  </div></div>`;
}
function compatSection(compat, incompat) {
  return `<div class="modal-section"><h3>🌿 Compatibilidades</h3><div class="compat-list">
    ${(compat||[]).map(i=>`<span class="compat-chip">✅ ${escHtml(i)}</span>`).join('')}
    ${(incompat||[]).map(i=>`<span class="compat-chip incompat-chip">❌ ${escHtml(i)}</span>`).join('')}
  </div></div>`;
}

// ── Utilitário ─────────────────────────────────────────────────
function escHtml(str) {
  return String(str ?? '')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#039;');
}

function commonsFilePageUrl(imageUrl) {
  if (!imageUrl) return '';
  try {
    const image = new URL(imageUrl, window.location.href);
    if (image.hostname !== 'upload.wikimedia.org') return '';
    const filename = decodeURIComponent(image.pathname.split('/').pop()).replace(/^\d+px-/, '').replace(/ /g, '_');
    return `https://commons.wikimedia.org/wiki/File:${encodeURIComponent(filename)}`;
  } catch (_) {
    return '';
  }
}

function handleImageError(img) {
  if (!img.dataset.originalFallback) {
    try {
      const imageUrl = new URL(img.src, window.location.href);
      if (imageUrl.hostname === 'upload.wikimedia.org' && imageUrl.pathname.includes('/thumb/')) {
        const filename = decodeURIComponent(imageUrl.pathname.split('/').pop()).replace(/^\d+px-/, '');
        img.dataset.originalFallback = '1';
        img.src = `https://commons.wikimedia.org/wiki/Special:FilePath/${encodeURIComponent(filename)}`;
        return;
      }
    } catch (_) { /* usa o estado visual de imagem indisponível */ }
  }
  img.hidden = true;
  img.parentElement?.classList.add('image-unavailable');
}

function ritualItemsHTML(items) {
  return `<div class="ritual-items">${items.map(name => {
    const herb = loadedHerbs.find(item => item.name.toLocaleLowerCase('pt-BR') === name.toLocaleLowerCase('pt-BR'));
    if (!herb?.img_url) return `<span class="ritual-item"><span class="ritual-item-fallback">🌿</span>${escHtml(name)}</span>`;
    return `<span class="ritual-item"><img src="${escHtml(herb.img_url)}" alt="" loading="lazy" decoding="async" onerror="handleImageError(this)">${escHtml(name)}</span>`;
  }).join('')}</div>`;
}
