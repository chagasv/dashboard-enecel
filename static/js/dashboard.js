// Configurações globais e referências de gráficos
let charts = {
    balanco: null,
    balancoCompA: null,
    balancoCompB: null,
    pld: null,
    ampereForward: null,
    ampereEvolution: null,
    enaSE: null,
    enaS: null,
    enaNE: null,
    enaN: null,
    enaCompSE: null,
    enaCompS: null,
    enaCompNE: null,
    enaCompN: null,
    cargaCompSIN: null,
    cargaCompSE: null,
    cargaCompS: null,
    cargaCompNE: null,
    cargaCompN: null,
    earCompSE: null,
    earCompS: null,
    earCompNE: null,
    earCompN: null
};

// Estado do modo comparativo do balanço, ampere e ena
let currentBalancoModo = 'simples';
let currentAmpereModo = 'forward';
let currentEnaModo = 'historico';
let currentAmpereFwView = 'chart';
let currentAmpereEvView = 'chart';

// Dados em cache para filtros dinâmicos
let rawBalancoData = null;
let rawPldHorarioData = null;
let rawAmpereCompletoData = null;
let rawBbceData = null;
let rawEnaData = null;
let rawCargaComparativoData = null;

// Inicialização da Página
document.addEventListener('DOMContentLoaded', () => {
    initTabNavigation();
    initDragAndDrop();
    initDragAndDropBbce();
    initSidebarToggle();
    fetchStatus();
    loadDashboardData();
});

// ----------------- CONTROLE DE ABAS -----------------
function initTabNavigation() {
    const navButtons = document.querySelectorAll('.nav-btn');
    navButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabName = btn.getAttribute('data-tab');
            switchTab(tabName);
        });
    });
}

function initSidebarToggle() {
    const toggleBtn = document.getElementById('sidebar-toggle');
    if (!toggleBtn) return;
    
    // Restaura o estado salvo no localStorage
    const isCollapsed = localStorage.getItem('sidebar-collapsed') === 'true';
    if (isCollapsed) {
        document.body.classList.add('sidebar-collapsed');
    }
    
    toggleBtn.addEventListener('click', () => {
        document.body.classList.toggle('sidebar-collapsed');
        const collapsed = document.body.classList.contains('sidebar-collapsed');
        localStorage.setItem('sidebar-collapsed', collapsed);
        
        // Redimensiona todos os gráficos ativos do Chart.js após o término da animação do CSS (200ms)
        setTimeout(() => {
            Object.values(charts).forEach(chart => {
                if (chart && typeof chart.resize === 'function') {
                    chart.resize();
                }
            });
        }, 200);
    });
}

function switchTab(tabId) {
    // Atualiza botões do menu lateral
    document.querySelectorAll('.nav-btn').forEach(btn => {
        if (btn.getAttribute('data-tab') === tabId) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    // Alterna visibilidade dos painéis de conteúdo
    document.querySelectorAll('.tab-pane').forEach(pane => {
        if (pane.id === `tab-${tabId}`) {
            pane.classList.add('active');
        } else {
            pane.classList.remove('active');
        }
    });

    // Atualiza cabeçalho
    const title = document.getElementById('page-title');
    const subtitle = document.getElementById('page-subtitle');
    
    switch (tabId) {
        case 'resumo':
            title.textContent = 'Visão Geral';
            subtitle.textContent = 'Status das bases de dados e resumos operacionais.';
            fetchStatus();
            break;
        case 'balanco':
            title.textContent = 'Balanço Energético';
            subtitle.textContent = 'Dados consolidados de geração e carga por subsistema da ONS.';
            if (currentBalancoModo === 'simples') {
                renderBalancoChart();
            } else {
                renderBalancoComparison();
            }
            break;
        case 'ena':
            title.textContent = 'ENA (Energia Natural Afluente)';
            subtitle.textContent = 'Energia Natural Afluente diária e comparativo de previsões com realizados.';
            if (currentEnaModo === 'historico') {
                renderEnaCharts();
            } else {
                loadEnaComparativoMeses();
            }
            break;
        case 'carga':
            title.textContent = 'Carga (Demanda de Energia)';
            subtitle.textContent = 'Comparativo de previsões com realizados semanais de Carga ONS.';
            loadCargaComparativoMeses();
            break;
        case 'ear':
            title.textContent = 'Reservatório (Energia Armazenada)';
            subtitle.textContent = 'Acompanhamento de Energia Armazenada (EAR) e comparação com previsões das RVs.';
            loadEarComparativoMeses();
            break;
        case 'ampere':
            title.textContent = 'Projeções Ampere';
            subtitle.textContent = 'Evolução histórica de rodadas e curvas forward da consultoria Ampere.';
            if (currentAmpereModo === 'forward') {
                renderAmpereForward();
            } else {
                renderAmpereEvolucao();
            }
            break;
        case 'etl':
            title.textContent = 'Painel de ETL';
            subtitle.textContent = 'Execução e monitoramento das rotinas diárias de atualização de dados.';
            fetchStatus();
            break;
        case 'auditoria':
            title.textContent = 'Conferir Dados';
            subtitle.textContent = 'Verificação rápida das últimas 100 linhas inseridas em cada planilha.';
            loadAuditoriaData();
            break;
        case 'bbce':
            title.textContent = 'Histórico BBCE';
            subtitle.textContent = 'Preços e volumes históricos negociados na BBCE.';
            loadBbceData();
            break;
    }
}

// ----------------- VISUALIZAÇÃO DE DADOS BRUTOS (AUDITORIA) -----------------
async function loadAuditoriaData() {
    const base = document.getElementById('auditoria-base-select').value;
    const tableHead = document.getElementById('auditoria-table-head');
    const tableBody = document.getElementById('auditoria-table-body');
    
    if (!tableHead || !tableBody) return;
    
    // Mostra loading
    tableHead.innerHTML = '<tr><th>Carregando...</th></tr>';
    tableBody.innerHTML = '<tr><td style="text-align: center; padding: 30px;"><i class="fa-solid fa-spinner fa-spin" style="font-size: 24px; color: var(--color-cyan);"></i> Buscando dados recentes...</td></tr>';
    
    try {
        const response = await fetch(`/api/data/view/${base}`);
        if (!response.ok) {
            throw new Error(`Falha na requisição: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        if (!data || data.length === 0) {
            tableHead.innerHTML = '<tr><th>Aviso</th></tr>';
            tableBody.innerHTML = '<tr><td style="text-align: center; padding: 30px; color: var(--text-muted);">Nenhum dado encontrado nesta base. Certifique-se de que os arquivos foram inicializados.</td></tr>';
            return;
        }
        
        // Renderiza cabeçalho e linhas baseado na base
        let headHtml = '';
        let bodyHtml = '';
        
        if (base === 'balanco') {
            headHtml = `
                <tr>
                    <th>Data/Hora</th>
                    <th>Subsistema</th>
                    <th style="text-align: right;">Geração Hidráulica (MWm)</th>
                    <th style="text-align: right;">Geração Térmica (MWm)</th>
                    <th style="text-align: right;">Geração Eólica (MWm)</th>
                    <th style="text-align: right;">Geração Solar (MWm)</th>
                    <th style="text-align: right;">Carga (MWm)</th>
                    <th style="text-align: right;">Intercâmbio (MWm)</th>
                </tr>
            `;
            
            data.forEach(row => {
                bodyHtml += `
                    <tr>
                        <td><strong>${row.din_instante}</strong></td>
                        <td><span class="indicator-badge arm">${row.id_subsistema}</span> (${row.nom_subsistema || ''})</td>
                        <td style="text-align: right;">${formatNumber(row.val_gerhidraulica, 3)}</td>
                        <td style="text-align: right;">${formatNumber(row.val_gertermica, 3)}</td>
                        <td style="text-align: right;">${formatNumber(row.val_gereolica, 3)}</td>
                        <td style="text-align: right;">${formatNumber(row.val_gersolar, 3)}</td>
                        <td style="text-align: right; font-weight: 600; color: #ef4444;">${formatNumber(row.val_carga, 3)}</td>
                        <td style="text-align: right;">${formatNumber(row.val_intercambio, 3)}</td>
                    </tr>
                `;
            });
            
        } else if (base === 'pld') {
            headHtml = `
                <tr>
                    <th>Mês Ref.</th>
                    <th>Submercado</th>
                    <th style="text-align: center;">Período Com.</th>
                    <th style="text-align: center;">Dia</th>
                    <th style="text-align: center;">Hora</th>
                    <th style="text-align: right;">PLD (R$/MWh)</th>
                </tr>
            `;
            
            data.forEach(row => {
                const mesStr = String(row.MES_REFERENCIA);
                const mesFormatado = `${mesStr.substring(4)}/${mesStr.substring(0, 4)}`;
                bodyHtml += `
                    <tr>
                        <td><strong>${mesFormatado}</strong></td>
                        <td><span class="indicator-badge pld">${row.SUBMERCADO}</span></td>
                        <td style="text-align: center;">${row.PERIODO_COMERCIALIZACAO}</td>
                        <td style="text-align: center;">${row.DIA}</td>
                        <td style="text-align: center;">${row.HORA}</td>
                        <td style="text-align: right; font-weight: 600; color: var(--color-orange);">${formatNumber(row.PLD_HORA, 2)}</td>
                    </tr>
                `;
            });
            
        } else if (base === 'ampere') {
            headHtml = `
                <tr>
                    <th>Rodada</th>
                    <th>Publicação</th>
                    <th>Indicador</th>
                    <th>Subsistema</th>
                    <th style="text-align: center;">Data Ref.</th>
                    <th style="text-align: center;">Unidade</th>
                    <th style="text-align: right;">Valor</th>
                </tr>
            `;
            
            data.forEach(row => {
                let badgeClass = 'arm';
                if (row.indicador === 'ENA') badgeClass = 'ena';
                if (row.indicador === 'PLD') badgeClass = 'pld';
                
                bodyHtml += `
                    <tr>
                        <td><strong>${row.rodada}</strong></td>
                        <td>${row.data_publicacao}</td>
                        <td><span class="indicator-badge ${badgeClass}">${row.indicador}</span></td>
                        <td>${row.subsistema || 'N/A'}</td>
                        <td style="text-align: center;">${row.data_referencia}</td>
                        <td style="text-align: center; color: var(--text-muted);">${row.unidade}</td>
                        <td style="text-align: right; font-weight: 600;">${formatNumber(row.valor, 2)}</td>
                    </tr>
                `;
            });
        } else if (base === 'bbce') {
            headHtml = `
                <tr>
                    <th>Data/Hora</th>
                    <th>Produto</th>
                    <th style="text-align: right;">Qtd Neg. (Q.N)</th>
                    <th>U.N.</th>
                    <th style="text-align: right;">Preço (R$/MWh)</th>
                    <th>Tipo Contrato</th>
                    <th>Tendência</th>
                    <th>Status</th>
                </tr>
            `;
            
            data.forEach(row => {
                let statusClass = 'arm';
                if (row.STATUS === 'Ativo') statusClass = 'ena';
                if (row.STATUS === 'Cancelado') statusClass = 'pld';
                
                bodyHtml += `
                    <tr>
                        <td><strong>${row['DATA/HORA']}</strong></td>
                        <td style="font-size: 12px; max-width: 250px; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">${row.PRODUTO}</td>
                        <td style="text-align: right;">${formatNumber(row['Q.N'], 2)}</td>
                        <td>${row['U.N.'] || ''}</td>
                        <td style="text-align: right; font-weight: 600; color: var(--color-green);">${formatNumber(row['PREÇO'], 2)}</td>
                        <td>${row['TIPO DE CONTRATO']}</td>
                        <td>${row['TENDÊNCIA'] || '-'}</td>
                        <td><span class="indicator-badge ${statusClass}">${row.STATUS}</span></td>
                    </tr>
                `;
            });
        } else if (base === 'ena') {
            headHtml = `
                <tr>
                    <th>Data</th>
                    <th>Subsistema</th>
                    <th style="text-align: right;">ENA Bruta (MWm)</th>
                    <th style="text-align: right;">ENA Bruta (% MLT)</th>
                    <th style="text-align: right;">ENA Armazenável (MWm)</th>
                    <th style="text-align: right;">ENA Armazenável (% MLT)</th>
                </tr>
            `;
            
            data.forEach(row => {
                bodyHtml += `
                    <tr>
                        <td><strong>${row.ena_data}</strong></td>
                        <td><span class="indicator-badge arm">${row.id_subsistema}</span> (${row.nom_subsistema || ''})</td>
                        <td style="text-align: right; font-weight: 600; color: #38bdf8;">${formatNumber(row.ena_bruta_regiao_mwmed, 2)}</td>
                        <td style="text-align: right; color: var(--color-orange);">${formatNumber(row.ena_bruta_regiao_percentualmlt, 2)}%</td>
                        <td style="text-align: right; font-weight: 600; color: #10b981;">${formatNumber(row.ena_armazenavel_regiao_mwmed, 2)}</td>
                        <td style="text-align: right; color: var(--color-purple);">${formatNumber(row.ena_armazenavel_regiao_percentualmlt, 2)}%</td>
                    </tr>
                `;
            });
        } else if (base === 'carga') {
            headHtml = `
                <tr>
                    <th>Data</th>
                    <th>Subsistema</th>
                    <th style="text-align: right;">Carga Média (MWm)</th>
                </tr>
            `;
            
            data.forEach(row => {
                bodyHtml += `
                    <tr>
                        <td><strong>${row.din_instante}</strong></td>
                        <td><span class="indicator-badge arm">${row.id_subsistema}</span> (${row.nom_subsistema || ''})</td>
                        <td style="text-align: right; font-weight: 600; color: var(--color-yellow);">${formatNumber(row.val_cargaenergiamwmed, 2)}</td>
                    </tr>
                `;
            });
        } else if (base === 'ear') {
            headHtml = `
                <tr>
                    <th>Data</th>
                    <th>Subsistema</th>
                    <th style="text-align: right;">Capacidade Máxima (MWmês)</th>
                    <th style="text-align: right;">EAR Verificada (MWmês)</th>
                    <th style="text-align: right;">EAR Verificada (%)</th>
                </tr>
            `;
            
            data.forEach(row => {
                bodyHtml += `
                    <tr>
                        <td><strong>${row.ear_data}</strong></td>
                        <td><span class="indicator-badge arm">${row.id_subsistema}</span> (${row.nom_subsistema || ''})</td>
                        <td style="text-align: right;">${formatNumber(row.ear_max_subsistema, 2)}</td>
                        <td style="text-align: right; font-weight: 600; color: var(--color-teal);">${formatNumber(row.ear_verif_subsistema_mwmes, 2)}</td>
                        <td style="text-align: right; color: var(--color-teal); font-weight: 600;">${formatNumber(row.ear_verif_subsistema_percentual, 2)}%</td>
                    </tr>
                `;
            });
        }
        
        tableHead.innerHTML = headHtml;
        tableBody.innerHTML = bodyHtml;
        
    } catch (error) {
        console.error("Erro ao carregar auditoria:", error);
        tableHead.innerHTML = '<tr><th>Erro</th></tr>';
        tableBody.innerHTML = `<tr><td style="text-align: center; padding: 30px; color: #f43f5e;"><i class="fa-solid fa-triangle-exclamation"></i> Falha ao carregar dados: ${error.message}</td></tr>`;
        showToast('Erro de Carregamento', 'Falha ao buscar os dados da tabela.', 'error');
    }
}

function formatNumber(val, decimals = 2) {
    if (val === undefined || val === null || val === '') return '-';
    const num = parseFloat(val);
    if (isNaN(num)) return val;
    return num.toLocaleString('pt-BR', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

// ----------------- BUSCA DE METADADOS / STATUS -----------------
async function fetchStatus() {
    try {
        const response = await fetch('/api/status');
        const status = await response.json();
        
        // Atualiza Cards de Visão Geral
        if (status.balanco && !status.balanco.status) {
            document.getElementById('status-balanco-data').textContent = status.balanco.max_data;
            document.getElementById('status-balanco-tamanho').textContent = status.balanco.tamanho;
            document.getElementById('status-balanco-linhas').textContent = status.balanco.linhas.toLocaleString('pt-BR');
            
            const etlBalanco = document.getElementById('etl-balanco-last');
            if (etlBalanco) etlBalanco.textContent = status.balanco.max_data;
        }
        
        if (status.pld && !status.pld.status) {
            document.getElementById('status-pld-data').textContent = status.pld.max_data;
            document.getElementById('status-pld-tamanho').textContent = status.pld.tamanho;
            document.getElementById('status-pld-linhas').textContent = status.pld.linhas.toLocaleString('pt-BR');
            
            const etlPld = document.getElementById('etl-pld-last');
            if (etlPld) etlPld.textContent = status.pld.max_data;
        }
        
        if (status.ena && !status.ena.status) {
            document.getElementById('status-ena-data').textContent = status.ena.max_data;
            document.getElementById('status-ena-tamanho').textContent = status.ena.tamanho;
            document.getElementById('status-ena-linhas').textContent = status.ena.linhas.toLocaleString('pt-BR');
            
            const etlEna = document.getElementById('etl-ena-last');
            if (etlEna) etlEna.textContent = status.ena.max_data;
        }
        
        if (status.carga && !status.carga.status) {
            document.getElementById('status-carga-data').textContent = status.carga.max_data;
            document.getElementById('status-carga-tamanho').textContent = status.carga.tamanho;
            document.getElementById('status-carga-linhas').textContent = status.carga.linhas.toLocaleString('pt-BR');
            
            const etlCarga = document.getElementById('etl-carga-last');
            if (etlCarga) etlCarga.textContent = status.carga.max_data;
        }
        
        if (status.ear && !status.ear.status) {
            document.getElementById('status-ear-data').textContent = status.ear.max_data;
            document.getElementById('status-ear-tamanho').textContent = status.ear.tamanho;
            document.getElementById('status-ear-linhas').textContent = status.ear.linhas.toLocaleString('pt-BR');
            
            const etlEar = document.getElementById('etl-ear-last');
            if (etlEar) etlEar.textContent = status.ear.max_data;
        }
        
        if (status.ampere && !status.ampere.status) {
            document.getElementById('status-ampere-data').textContent = status.ampere.max_data;
            document.getElementById('status-ampere-tamanho').textContent = status.ampere.tamanho;
            document.getElementById('status-ampere-linhas').textContent = status.ampere.linhas.toLocaleString('pt-BR');
        }
        
        if (status.bbce && !status.bbce.status) {
            document.getElementById('status-bbce-data').textContent = status.bbce.max_data;
            document.getElementById('status-bbce-tamanho').textContent = status.bbce.tamanho;
            document.getElementById('status-bbce-linhas').textContent = status.bbce.linhas.toLocaleString('pt-BR');
            
            const etlBbce = document.getElementById('etl-bbce-last');
            if (etlBbce) etlBbce.textContent = status.bbce.max_data;
        }
    } catch (error) {
        console.error("Erro ao buscar status:", error);
    }
}

// ----------------- CARREGAMENTO DOS DADOS PARA GRÁFICOS -----------------
async function loadPldHorarioData() {
    try {
        const response = await fetch('/api/data/pld_horario');
        if (response.ok) {
            rawPldHorarioData = await response.json();
        }
    } catch (error) {
        console.error("Erro ao carregar dados do PLD horário:", error);
    }
}

async function loadDashboardData() {
    await loadPldHorarioData();
    loadBalancoData();
    loadPldData();
    loadAmpereCompletoData();
    loadBbceData();
    loadEnaData();
}

// ENA Diária (ONS)
async function loadEnaData() {
    try {
        const response = await fetch('/api/data/ena');
        if (response.ok) {
            rawEnaData = await response.json();
            
            // Se a aba ENA estiver ativa, renderiza os gráficos
            const enaBtn = document.querySelector('.nav-btn[data-tab="ena"]');
            if (enaBtn && enaBtn.classList.contains('active')) {
                renderEnaCharts();
            }
        }
    } catch (error) {
        console.error("Erro ao carregar dados da ENA:", error);
    }
}

function renderEnaCharts() {
    if (!rawEnaData) return;
    
    // Obtém a variável selecionada no filtro do cabeçalho
    const varSelect = document.getElementById('ena-variavel-select');
    const variavel = varSelect ? varSelect.value : 'armazenavel';
    
    const subsistemas = [
        { id: 'SE', chartId: 'chart-ena-se', chartRef: 'enaSE' },
        { id: 'S', chartId: 'chart-ena-s', chartRef: 'enaS' },
        { id: 'NE', chartId: 'chart-ena-ne', chartRef: 'enaNE' },
        { id: 'N', chartId: 'chart-ena-n', chartRef: 'enaN' }
    ];
    
    subsistemas.forEach(subInfo => {
        const subData = rawEnaData[subInfo.id];
        if (!subData) return;
        
        const canvas = document.getElementById(subInfo.chartId);
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        
        if (charts[subInfo.chartRef]) {
            charts[subInfo.chartRef].destroy();
        }
        
        // Formata as datas do eixo X para DD/MM
        const labelsFormatados = subData.labels.map(l => {
            const partes = l.split('-');
            if (partes.length === 3) {
                return `${partes[2]}/${partes[1]}`;
            }
            return l;
        });
        
        // Define os datasets dinamicamente baseados na seleção do usuário
        let datasets = [];
        if (variavel === 'armazenavel') {
            datasets = [
                {
                    label: 'Armazenável (MWm)',
                    data: subData.ena_armazenavel_mwmed,
                    borderColor: '#10b981', // Verde
                    backgroundColor: 'rgba(16, 185, 129, 0.05)',
                    borderWidth: 2,
                    yAxisID: 'y',
                    tension: 0.15,
                    fill: true,
                    pointRadius: 1,
                    pointHoverRadius: 4
                },
                {
                    label: 'Armazenável (% MLT)',
                    data: subData.ena_armazenavel_percentualmlt,
                    borderColor: '#a855f7', // Roxo
                    borderDash: [5, 5],
                    backgroundColor: 'transparent',
                    borderWidth: 1.5,
                    yAxisID: 'y1',
                    tension: 0.1,
                    pointRadius: 0,
                    pointHoverRadius: 3
                }
            ];
        } else {
            datasets = [
                {
                    label: 'Bruta (MWm)',
                    data: subData.ena_bruta_mwmed,
                    borderColor: '#38bdf8', // Ciano
                    backgroundColor: 'rgba(56, 189, 248, 0.05)',
                    borderWidth: 2,
                    yAxisID: 'y',
                    tension: 0.15,
                    fill: true,
                    pointRadius: 1,
                    pointHoverRadius: 4
                },
                {
                    label: 'Bruta (% MLT)',
                    data: subData.ena_bruta_percentualmlt,
                    borderColor: '#f97316', // Laranja
                    borderDash: [5, 5],
                    backgroundColor: 'transparent',
                    borderWidth: 1.5,
                    yAxisID: 'y1',
                    tension: 0.1,
                    pointRadius: 0,
                    pointHoverRadius: 3
                }
            ];
        }
        
        charts[subInfo.chartRef] = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labelsFormatados,
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(255, 255, 255, 0.03)' },
                        ticks: { color: '#a1a1aa', font: { family: 'Inter', size: 10 }, maxTicksLimit: 12 }
                    },
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        title: {
                            display: true,
                            text: 'MWmedio',
                            color: '#a1a1aa',
                            font: { family: 'Inter', size: 10 }
                        },
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#a1a1aa', font: { family: 'Inter', size: 10 } }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        title: {
                            display: true,
                            text: '% MLT',
                            color: '#a1a1aa',
                            font: { family: 'Inter', size: 10 }
                        },
                        grid: { drawOnChartArea: false },
                        ticks: {
                            color: '#a1a1aa',
                            font: { family: 'Inter', size: 10 },
                            callback: function(value) { return value + '%'; }
                        }
                    }
                },
                plugins: {
                    legend: {
                        labels: { color: '#f4f4f5', font: { family: 'Inter', size: 10 }, boxWidth: 12 }
                    },
                    tooltip: {
                        backgroundColor: '#18181b',
                        titleColor: '#f4f4f5',
                        bodyColor: '#a1a1aa',
                        borderColor: '#27272a',
                        borderWidth: 1
                    }
                }
            }
        });
    });
}

// 1. Balanço Energético (ONS)
async function loadBalancoData() {
    try {
        const response = await fetch('/api/data/balanco');
        if (response.ok) {
            rawBalancoData = await response.json();
            
            // Inicializa limites e valor padrão dos seletores de data
            if (rawBalancoData && rawBalancoData.length > 0) {
                const datasUnicas = [...new Set(rawBalancoData.map(d => d.din_instante.split(' ')[0]))].sort();
                if (datasUnicas.length > 0) {
                    const minDate = datasUnicas[0];
                    const maxDate = datasUnicas[datasUnicas.length - 1];
                    const prevDate = datasUnicas.length > 1 ? datasUnicas[datasUnicas.length - 2] : maxDate;
                    
                    // Seletor simples
                    const dataInput = document.getElementById('balanco-data-input');
                    if (dataInput) {
                        dataInput.min = minDate;
                        dataInput.max = maxDate;
                        dataInput.value = maxDate; // padrão é o dia mais recente
                    }
                    
                    // Seletor comparativo A
                    const compADataInput = document.getElementById('comp-a-data-input');
                    if (compADataInput) {
                        compADataInput.min = minDate;
                        compADataInput.max = maxDate;
                        compADataInput.value = maxDate;
                    }
                    
                    // Seletor comparativo B
                    const compBDataInput = document.getElementById('comp-b-data-input');
                    if (compBDataInput) {
                        compBDataInput.min = minDate;
                        compBDataInput.max = maxDate;
                        compBDataInput.value = prevDate; // padrão é o dia anterior (D-1)
                    }
                }
            }
            
            if (currentBalancoModo === 'simples') {
                renderBalancoChart();
            } else {
                renderBalancoComparison();
            }
        }
    } catch (error) {
        console.error("Erro ao carregar dados do balanço:", error);
    }
}

function renderBalancoChart() {
    if (!rawBalancoData) return;
    
    const sub = document.getElementById('balanco-sub-select').value; // ex: SE, S, NE, N
    const dataInput = document.getElementById('balanco-data-input');
    const dataSelecionada = dataInput ? dataInput.value : ''; // ex: YYYY-MM-DD
    
    if (!dataSelecionada) return;
    
    // Filtra dados para o subsistema escolhido e para o dia selecionado
    let filtered = rawBalancoData.filter(d => d.id_subsistema === sub && d.din_instante.startsWith(dataSelecionada));
    
    // Garante ordenação cronológica horária
    filtered.sort((a, b) => a.din_instante.localeCompare(b.din_instante));
    
    // Prepara datasets para Chart.js - eixo X com as horas (HH:MM)
    const labels = filtered.map(d => d.din_instante.split(' ')[1]);
    const gerHidraulica = filtered.map(d => d.val_gerhidraulica || 0);
    const gerTermica = filtered.map(d => d.val_gertermica || 0);
    const gerEolica = filtered.map(d => d.val_gereolica || 0);
    const gerSolar = filtered.map(d => d.val_gersolar || 0);
    const carga = filtered.map(d => d.val_carga || 0);
    
    // Calcula as médias diárias para o subsistema e dia filtrados
    let sumHid = 0, sumTer = 0, sumEol = 0, sumSol = 0, sumCarga = 0, sumInter = 0;
    const count = filtered.length;
    
    filtered.forEach(d => {
        sumHid += d.val_gerhidraulica || 0;
        sumTer += d.val_gertermica || 0;
        sumEol += d.val_gereolica || 0;
        sumSol += d.val_gersolar || 0;
        sumCarga += d.val_carga || 0;
        sumInter += d.val_intercambio || 0;
    });
    
    const avgHid = count > 0 ? sumHid / count : 0;
    const avgTer = count > 0 ? sumTer / count : 0;
    const avgEol = count > 0 ? sumEol / count : 0;
    const avgSol = count > 0 ? sumSol / count : 0;
    const avgCarga = count > 0 ? sumCarga / count : 0;
    const avgInter = count > 0 ? sumInter / count : 0;
    const avgTotalGer = avgHid + avgTer + avgEol + avgSol;
    
    // Atualiza as médias nos elementos de card no DOM (arredondado para inteiro)
    const elTotal = document.getElementById('avg-geracao-total');
    const elCarga = document.getElementById('avg-carga');
    const elHid = document.getElementById('avg-ger-hidraulica');
    const elTer = document.getElementById('avg-ger-termica');
    const elEol = document.getElementById('avg-ger-eolica');
    const elSol = document.getElementById('avg-ger-solar');
    const elInter = document.getElementById('avg-intercambio');
    
    if (elTotal) elTotal.textContent = formatNumber(avgTotalGer, 0);
    if (elCarga) elCarga.textContent = formatNumber(avgCarga, 0);
    if (elHid) elHid.textContent = formatNumber(avgHid, 0);
    if (elTer) elTer.textContent = formatNumber(avgTer, 0);
    if (elEol) elEol.textContent = formatNumber(avgEol, 0);
    if (elSol) elSol.textContent = formatNumber(avgSol, 0);
    if (elInter) elInter.textContent = formatNumber(avgInter, 0);

    // Atualiza o card de PLD Médio
    const submercado = getSubmercadoBySubsistema(sub);
    const avgPld = calculateAvgPld(submercado, dataSelecionada);
    const elAvgPld = document.getElementById('avg-pld-diario');
    if (elAvgPld) {
        if (avgPld !== null) {
            elAvgPld.textContent = `R$ ${formatNumber(avgPld, 0)}`;
        } else {
            elAvgPld.textContent = '-';
        }
    }
    
    // Renderiza a faixa de PLD Horário
    renderPldStrip('pld-strip-simples', 'pld-strip-grid-simples', submercado, dataSelecionada);

    // Calcula e atualiza os limites mínimos e máximos com as respectivas horas
    const extTotalGer = d => (d.val_gerhidraulica || 0) + (d.val_gertermica || 0) + (d.val_gereolica || 0) + (d.val_gersolar || 0);
    const extCarga = d => d.val_carga || 0;
    const extHid = d => d.val_gerhidraulica || 0;
    const extTer = d => d.val_gertermica || 0;
    const extEol = d => d.val_gereolica || 0;
    const extSol = d => d.val_gersolar || 0;
    const extInter = d => d.val_intercambio || 0;
    
    const statsTotal = findMinMax(filtered, extTotalGer);
    const statsCarga = findMinMax(filtered, extCarga);
    const statsHid = findMinMax(filtered, extHid);
    const statsTer = findMinMax(filtered, extTer);
    const statsEol = findMinMax(filtered, extEol);
    const statsSol = findMinMax(filtered, extSol);
    const statsInter = findMinMax(filtered, extInter);
    
    updateMinMaxDOM('geracao-total', statsTotal);
    updateMinMaxDOM('carga', statsCarga);
    updateMinMaxDOM('ger-hidraulica', statsHid);
    updateMinMaxDOM('ger-termica', statsTer);
    updateMinMaxDOM('ger-eolica', statsEol);
    updateMinMaxDOM('ger-solar', statsSol);
    updateMinMaxDOM('intercambio', statsInter);
    
    const ctx = document.getElementById('chart-balanco').getContext('2d');
    
    if (charts.balanco) {
        charts.balanco.destroy();
    }
    
    charts.balanco = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Carga Total',
                    data: carga,
                    borderColor: '#f43f5e',
                    borderWidth: 3,
                    pointRadius: 1,
                    pointHoverRadius: 4,
                    fill: false,
                    tension: 0.15,
                    stack: 'carga',
                    order: 0
                },
                {
                    label: 'Geração Térmica',
                    data: gerTermica,
                    borderColor: '#f97316',
                    backgroundColor: 'rgba(249, 115, 22, 0.08)',
                    borderWidth: 1.5,
                    pointRadius: 0,
                    pointHoverRadius: 3,
                    fill: true,
                    stack: 'geracao',
                    order: 1
                },
                {
                    label: 'Geração Solar',
                    data: gerSolar,
                    borderColor: '#eab308',
                    backgroundColor: 'rgba(234, 179, 8, 0.08)',
                    borderWidth: 1.5,
                    pointRadius: 0,
                    pointHoverRadius: 3,
                    fill: true,
                    stack: 'geracao',
                    order: 2
                },
                {
                    label: 'Geração Hidráulica',
                    data: gerHidraulica,
                    borderColor: '#38bdf8',
                    backgroundColor: 'rgba(56, 189, 248, 0.08)',
                    borderWidth: 1.5,
                    pointRadius: 0,
                    pointHoverRadius: 3,
                    fill: true,
                    stack: 'geracao',
                    order: 3
                },
                {
                    label: 'Geração Eólica',
                    data: gerEolica,
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.08)',
                    borderWidth: 1.5,
                    pointRadius: 0,
                    pointHoverRadius: 3,
                    fill: true,
                    stack: 'geracao',
                    order: 4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#94a3b8' }
                },
                y: {
                    stacked: true,
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#94a3b8' }
                }
            },
            plugins: {
                legend: {
                    labels: { color: '#f8fafc', font: { family: 'Inter' } }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false
                }
            }
        }
    });
}

// 2. PLD Horário (CCEE)
async function loadPldData() {
    try {
        const response = await fetch('/api/data/pld');
        if (response.ok) {
            const data = await response.json(); // Estrutura { SUBMERCADO: {labels: [], valores: []} }
            
            const periodSelect = document.getElementById('pld-periodo-select');
            const period = periodSelect ? parseInt(periodSelect.value) : 60;
            
            const ctx = document.getElementById('chart-pld').getContext('2d');
            if (charts.pld) {
                charts.pld.destroy();
            }
            
            // Cria os datasets
            const colors = {
                'SUDESTE': '#a855f7',
                'SUL': '#3b82f6',
                'NORDESTE': '#10b981',
                'NORTE': '#eab308'
            };
            
            const datasets = [];
            let labels = [];
            
            for (const sub in data) {
                // Filtra os últimos N dias (period)
                const subLabels = data[sub].labels.slice(-period);
                const subValores = data[sub].valores.slice(-period);
                
                if (labels.length === 0) {
                    labels = subLabels.map(l => formatDateString(l));
                }
                
                let pointRadius = 2;
                if (period <= 15) pointRadius = 4;
                else if (period >= 180) pointRadius = 0.5;
                
                datasets.push({
                    label: sub,
                    data: subValores,
                    borderColor: colors[sub] || '#64748b',
                    backgroundColor: 'transparent',
                    borderWidth: 2.5,
                    pointRadius: pointRadius,
                    tension: 0.1
                });
            }
            
            // Atualiza o indicador de período na legenda do gráfico
            const elUnitIndicator = document.querySelector('#tab-pld .unit-indicator');
            if (elUnitIndicator) {
                elUnitIndicator.textContent = `Unidade: R$/MWh (Média Diária dos Últimos ${period} Dias)`;
            }
            
            charts.pld = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: datasets
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            grid: { color: 'rgba(255, 255, 255, 0.05)' },
                            ticks: { color: '#94a3b8' }
                        },
                        y: {
                            grid: { color: 'rgba(255, 255, 255, 0.05)' },
                            ticks: { color: '#94a3b8' }
                        }
                    },
                    plugins: {
                        legend: {
                            labels: { color: '#f8fafc' }
                        }
                    }
                }
            });
        }
    } catch (error) {
        console.error("Erro ao carregar dados do PLD:", error);
    }
}

// 3. Projeções Ampere
async function loadAmpereCompletoData() {
    try {
        const response = await fetch('/api/data/ampere_completo');
        if (response.ok) {
            rawAmpereCompletoData = await response.json();
            initAmpereControls();
        }
    } catch (error) {
        console.error("Erro ao carregar dados históricos da Ampere:", error);
    }
}

function initAmpereControls() {
    if (!rawAmpereCompletoData || rawAmpereCompletoData.length === 0) return;
    
    // 1. Popula as rodadas (Curva Forward)
    const rodadasUnicas = [...new Set(rawAmpereCompletoData.map(d => d.rodada))].sort((a, b) => b - a);
    const container = document.getElementById('ampere-fw-rodadas-container');
    
    if (container) {
        let html = '';
        rodadasUnicas.forEach((rod, idx) => {
            const checked = idx < 3 ? 'checked' : '';
            const rodStr = String(rod);
            const formattedRod = `${rodStr.substring(6,8)}/${rodStr.substring(4,6)}/${rodStr.substring(0,4)}`;
            
            html += `
                <label class="checkbox-item">
                    <input type="checkbox" value="${rod}" ${checked} onchange="renderAmpereForward()">
                    <span>Rodada ${formattedRod}</span>
                </label>
            `;
        });
        container.innerHTML = html;
    }
    
    // 2. Popula os produtos/meses (Evolução)
    const produtosUnicas = [...new Set(rawAmpereCompletoData.map(d => d.data_referencia))].sort();
    const selectProduto = document.getElementById('ampere-ev-produto');
    
    if (selectProduto) {
        let html = '';
        produtosUnicas.forEach(prod => {
            const label = formatMonthYear(prod);
            html += `<option value="${prod}">${label}</option>`;
        });
        selectProduto.innerHTML = html;
        
        if (produtosUnicas.length > 0) {
            selectProduto.value = produtosUnicas[0];
        }
    }
    
    // Renderiza a visualização inicial
    renderAmpereForward();
    renderAmpereEvolucao();
}

function toggleAllFwRodadas(checked) {
    const checkboxes = document.querySelectorAll('#ampere-fw-rodadas-container input[type="checkbox"]');
    checkboxes.forEach(cb => {
        cb.checked = checked;
    });
    renderAmpereForward();
}

function switchAmpereModo(modo) {
    currentAmpereModo = modo;
    
    const btnFw = document.getElementById('subtab-ampere-forward');
    const btnEv = document.getElementById('subtab-ampere-evolucao');
    const painelFw = document.getElementById('ampere-painel-forward');
    const painelEv = document.getElementById('ampere-painel-evolucao');
    
    if (btnFw && btnEv && painelFw && painelEv) {
        if (modo === 'forward') {
            btnFw.classList.add('active');
            btnEv.classList.remove('active');
            painelFw.style.display = 'block';
            painelEv.style.display = 'none';
            renderAmpereForward();
        } else {
            btnFw.classList.remove('active');
            btnEv.classList.add('active');
            painelFw.style.display = 'none';
            painelEv.style.display = 'block';
            renderAmpereEvolucao();
        }
    }
}

function setAmpereFwView(view) {
    currentAmpereFwView = view;
    const btnChart = document.getElementById('segment-fw-chart');
    const btnTable = document.getElementById('segment-fw-table');
    const chartContainer = document.getElementById('ampere-fw-chart-container');
    const tableContainer = document.getElementById('ampere-fw-table-container');
    
    if (btnChart && btnTable && chartContainer && tableContainer) {
        if (view === 'chart') {
            btnChart.classList.add('active');
            btnTable.classList.remove('active');
            chartContainer.style.display = 'block';
            tableContainer.style.display = 'none';
            renderAmpereForward();
        } else {
            btnChart.classList.remove('active');
            btnTable.classList.add('active');
            chartContainer.style.display = 'none';
            tableContainer.style.display = 'block';
            renderAmpereForward();
        }
    }
}

function setAmpereEvView(view) {
    currentAmpereEvView = view;
    const btnChart = document.getElementById('segment-ev-chart');
    const btnTable = document.getElementById('segment-ev-table');
    const chartContainer = document.getElementById('ampere-ev-chart-container');
    const tableContainer = document.getElementById('ampere-ev-table-container');
    
    if (btnChart && btnTable && chartContainer && tableContainer) {
        if (view === 'chart') {
            btnChart.classList.add('active');
            btnTable.classList.remove('active');
            chartContainer.style.display = 'block';
            tableContainer.style.display = 'none';
            renderAmpereEvolucao();
        } else {
            btnChart.classList.remove('active');
            btnTable.classList.add('active');
            chartContainer.style.display = 'none';
            tableContainer.style.display = 'block';
            renderAmpereEvolucao();
        }
    }
}

function renderAmpereForward() {
    if (!rawAmpereCompletoData) return;
    
    const indicatorVal = document.getElementById('ampere-fw-indicador').value;
    const parts = indicatorVal.split('-');
    const indicador = parts[0];
    const unidade = parts[1];
    const subsistema = document.getElementById('ampere-fw-subsistema').value;
    
    // Pega as rodadas selecionadas
    const selectedRodadas = Array.from(document.querySelectorAll('#ampere-fw-rodadas-container input[type="checkbox"]:checked'))
        .map(cb => parseInt(cb.value));
        
    // Filtra dados correspondentes
    const filtered = rawAmpereCompletoData.filter(d => 
        d.indicador === indicador && 
        d.unidade === unidade && 
        d.subsistema === subsistema && 
        selectedRodadas.includes(d.rodada)
    );
    
    // Meses únicos para o Eixo X
    const uniqueMonths = [...new Set(filtered.map(d => d.data_referencia))].sort();
    
    // Se a visualização for tabela
    if (currentAmpereFwView === 'table') {
        const table = document.getElementById('ampere-fw-table');
        if (table) {
            let headHtml = '<tr><th>Rodada / Publicação</th>';
            uniqueMonths.forEach(m => {
                headHtml += `<th style="text-align: right;">${formatMonthYear(m)}</th>`;
            });
            headHtml += '</tr>';
            
            let bodyHtml = '';
            // Ordena rodadas decrescente na tabela
            [...selectedRodadas].sort((a, b) => b - a).forEach(rod => {
                const rodStr = String(rod);
                const formattedRod = `${rodStr.substring(6,8)}/${rodStr.substring(4,6)}/${rodStr.substring(0,4)}`;
                
                bodyHtml += `<tr><td><strong>Rodada ${formattedRod}</strong></td>`;
                uniqueMonths.forEach(m => {
                    const item = filtered.find(d => d.rodada === rod && d.data_referencia === m);
                    const val = item ? item.valor : null;
                    bodyHtml += `<td style="text-align: right; font-weight: 500;">${formatNumber(val, 1)}</td>`;
                });
                bodyHtml += '</tr>';
            });
            
            table.innerHTML = `<thead>${headHtml}</thead><tbody>${bodyHtml}</tbody>`;
        }
        return;
    }
    
    // Se a visualização for gráfico
    const labels = uniqueMonths.map(m => formatMonthYear(m));
    const colors = ['#a855f7', '#3b82f6', '#10b981', '#eab308', '#f43f5e', '#06b6d4', '#f97316', '#ec4899'];
    
    const datasets = [];
    selectedRodadas.sort((a, b) => b - a).forEach((rod, idx) => {
        const rodStr = String(rod);
        const formattedRod = `${rodStr.substring(6,8)}/${rodStr.substring(4,6)}/${rodStr.substring(0,4)}`;
        
        // Mapeia os valores para cada mês ordenado
        const dataVals = uniqueMonths.map(m => {
            const item = filtered.find(d => d.rodada === rod && d.data_referencia === m);
            return item ? item.valor : null;
        });
        
        datasets.push({
            label: `Rodada ${formattedRod}`,
            data: dataVals,
            borderColor: colors[idx % colors.length],
            backgroundColor: 'transparent',
            borderWidth: 2.5,
            pointRadius: 3,
            tension: 0.15
        });
    });
    
    // Atualiza a legenda de unidade
    const elLegend = document.getElementById('ampere-fw-chart-legend');
    if (elLegend) {
        elLegend.textContent = `Unidade: ${unidade} (${subsistema})`;
    }
    
    const ctx = document.getElementById('chart-ampere-forward').getContext('2d');
    if (charts.ampereForward) {
        charts.ampereForward.destroy();
    }
    
    charts.ampereForward = new Chart(ctx, {
        type: 'line',
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94a3b8' } },
                y: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94a3b8' } }
            },
            plugins: {
                legend: { position: 'bottom', labels: { color: '#f8fafc', font: { size: 10 } } }
            }
        }
    });
}

function renderAmpereEvolucao() {
    if (!rawAmpereCompletoData) return;
    
    const indicatorVal = document.getElementById('ampere-ev-indicador').value;
    const parts = indicatorVal.split('-');
    const indicador = parts[0];
    const unidade = parts[1];
    const subsistema = document.getElementById('ampere-ev-subsistema').value;
    const produto = document.getElementById('ampere-ev-produto').value;
    
    if (!produto) return;
    
    // Filtra dados correspondentes
    const filtered = rawAmpereCompletoData.filter(d => 
        d.indicador === indicador && 
        d.unidade === unidade && 
        d.subsistema === subsistema && 
        d.data_referencia === produto
    );
    
    // Ordena por rodada cronológica para o gráfico e evolução natural
    const sorted = [...filtered].sort((a, b) => a.rodada - b.rodada);
    
    // Se a visualização for tabela
    if (currentAmpereEvView === 'table') {
        const table = document.getElementById('ampere-ev-table');
        if (table) {
            let headHtml = `
                <tr>
                    <th>Rodada / Publicação</th>
                    <th>Data Publicação</th>
                    <th style="text-align: right;">Valor Projetado (${unidade})</th>
                </tr>
            `;
            
            let bodyHtml = '';
            // Tabela ordenada do mais recente para o mais antigo (rodada desc)
            const sortedDesc = [...filtered].sort((a, b) => b.rodada - a.rodada);
            sortedDesc.forEach(d => {
                const rodStr = String(d.rodada);
                const formattedRod = `${rodStr.substring(6,8)}/${rodStr.substring(4,6)}/${rodStr.substring(0,4)}`;
                
                let formattedPub = d.data_publicacao;
                if (/^\d{4}-\d{2}-\d{2}/.test(d.data_publicacao)) {
                    const parts = d.data_publicacao.split(' ')[0].split('-');
                    formattedPub = `${parts[2]}/${parts[1]}/${parts[0]}`;
                }
                
                bodyHtml += `
                    <tr>
                        <td><strong>Rodada ${formattedRod}</strong></td>
                        <td>${formattedPub}</td>
                        <td style="text-align: right; font-weight: 600; color: var(--color-purple);">${formatNumber(d.valor, 1)}</td>
                    </tr>
                `;
            });
            
            table.innerHTML = `<thead>${headHtml}</thead><tbody>${bodyHtml}</tbody>`;
        }
        return;
    }
    
    // Se a visualização for gráfico
    const labels = sorted.map(d => {
        const rodStr = String(d.rodada);
        return `${rodStr.substring(6,8)}/${rodStr.substring(4,6)}`;
    });
    
    const datasets = [{
        label: `Projeção para ${formatMonthYear(produto)}`,
        data: sorted.map(d => d.valor),
        borderColor: '#a855f7',
        backgroundColor: 'rgba(168, 85, 247, 0.1)',
        borderWidth: 3,
        pointRadius: 5,
        pointHoverRadius: 8,
        fill: true,
        tension: 0.1
    }];
    
    // Atualiza a legenda de unidade
    const elLegend = document.getElementById('ampere-ev-chart-legend');
    if (elLegend) {
        elLegend.textContent = `Unidade: ${unidade} (${subsistema} - Produto: ${formatMonthYear(produto)})`;
    }
    
    const ctx = document.getElementById('chart-ampere-evolution').getContext('2d');
    if (charts.ampereEvolution) {
        charts.ampereEvolution.destroy();
    }
    
    charts.ampereEvolution = new Chart(ctx, {
        type: 'line',
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94a3b8' } },
                y: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94a3b8' } }
            },
            plugins: {
                legend: { position: 'bottom', labels: { color: '#f8fafc' } }
            }
        }
    });
}


// ----------------- ROTINAS DE ETL (BOTOES DE SYNC) -----------------
async function runETL(type) {
    let btn, logPrefix, url;
    
    if (type === 'balanco') {
        btn = document.getElementById('btn-sync-balanco');
        logPrefix = 'Balanço Energético (ONS)';
        url = '/api/update/balanco';
    } else if (type === 'pld') {
        btn = document.getElementById('btn-sync-pld');
        logPrefix = 'PLD Horário (CCEE)';
        url = '/api/update/pld';
    } else if (type === 'ena') {
        btn = document.getElementById('btn-sync-ena');
        logPrefix = 'ENA (ONS)';
        url = '/api/update/ena';
    } else if (type === 'carga') {
        btn = document.getElementById('btn-sync-carga');
        logPrefix = 'Carga (ONS)';
        url = '/api/update/carga';
    } else if (type === 'ear') {
        btn = document.getElementById('btn-sync-ear');
        logPrefix = 'Reservatório EAR (ONS)';
        url = '/api/update/ear';
    }
    
    if (!btn) return;
    
    // Bloqueia botao e mostra progresso
    btn.disabled = true;
    const originalText = btn.innerHTML;
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Processando...`;
    
    appendLog(`[SISTEMA] Iniciando requisição para atualizar ${logPrefix}...`, 'system');
    
    try {
        const response = await fetch(url, { method: 'POST' });
        
        if (!response.ok) {
            const errorText = await response.text();
            // Limpa as tags HTML do erro para exibir texto puro
            const preview = errorText.replace(/<[^>]*>/g, '').replace(/\s+/g, ' ').substring(0, 150).trim();
            throw new Error(`Código ${response.status}: ${preview || response.statusText}`);
        }
        
        const res = await response.json();
        
        if (res.success) {
            appendLog(`[SUCESSO] ${res.message}`, 'success');
            appendLog(`  - Registros novos: ${res.novos_registros.toLocaleString('pt-BR')}`, 'info');
            appendLog(`  - Registros totais: ${res.total_registros.toLocaleString('pt-BR')}`, 'info');
            showToast('Sucesso', `${logPrefix} atualizado com sucesso!`, 'success');
            
            // Recarrega status e gráficos
            fetchStatus();
            if (type === 'balanco') loadBalancoData();
            if (type === 'pld') loadPldData();
            if (type === 'ena') {
                if (currentEnaModo === 'historico') {
                    renderEnaCharts();
                } else {
                    loadEnaComparativoData();
                }
            }
            if (type === 'carga') {
                loadCargaComparativoData();
            }
            if (type === 'ear') {
                loadEarComparativoData();
            }
        } else {
            appendLog(`[ERRO] Falha ao atualizar: ${res.message}`, 'error');
            showToast('Erro', `Falha ao atualizar ${logPrefix}. Verifique o console.`, 'error');
        }
    } catch (error) {
        appendLog(`[ERRO] Falha de comunicação com o servidor: ${error.message}`, 'error');
        showToast('Erro de Rede', 'Não foi possível completar a operação no servidor.', 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

// ----------------- DRAG AND DROP / UPLOAD PDF AMPERE -----------------
let selectedPDFFile = null;

function initDragAndDrop() {
    const dropzone = document.getElementById('pdf-dropzone');
    const fileInput = document.getElementById('pdf-file-input');
    
    if (!dropzone || !fileInput) return;
    
    dropzone.addEventListener('click', () => fileInput.click());
    
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleSelectedFile(e.target.files[0]);
        }
    });
    
    // Eventos de drag
    ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.add('dragover');
        }, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.remove('dragover');
        }, false);
    });
    
    dropzone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            handleSelectedFile(files[0]);
        }
    });
}

function handleSelectedFile(file) {
    if (!file.name.toLowerCase().endswith('.pdf')) {
        showToast('Formato Inválido', 'O arquivo selecionado deve ser um relatório em formato PDF.', 'error');
        return;
    }
    
    selectedPDFFile = file;
    document.getElementById('pdf-dropzone').style.display = 'none';
    document.getElementById('selected-file-area').style.display = 'flex';
    document.getElementById('selected-file-name').textContent = file.name;
    
    appendLog(`[SISTEMA] Arquivo PDF selecionado: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`, 'system');
}

function clearSelectedFile() {
    selectedPDFFile = null;
    document.getElementById('pdf-file-input').value = '';
    document.getElementById('pdf-dropzone').style.display = 'block';
    document.getElementById('selected-file-area').style.display = 'none';
    appendLog(`[SISTEMA] Seleção de arquivo cancelada.`, 'system');
}

async function uploadAmperePDF() {
    if (!selectedPDFFile) return;
    
    const btn = document.getElementById('btn-upload-ampere');
    btn.disabled = true;
    const originalText = btn.innerHTML;
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Processando PDF...`;
    
    appendLog(`[SISTEMA] Iniciando processamento do PDF da Ampere...`, 'system');
    
    const formData = new FormData();
    formData.append('file', selectedPDFFile);
    
    try {
        const response = await fetch('/api/update/ampere', {
            method: 'POST',
            body: formData
        });
        
        const res = await response.json();
        
        if (res.success) {
            appendLog(`[SUCESSO] ${res.message}`, 'success');
            appendLog(`  - Linhas extraídas e adicionadas: ${res.novos_registros}`, 'info');
            appendLog(`  - Total geral de linhas agora: ${res.total_registros}`, 'info');
            showToast('Sucesso', 'Relatório Ampere processado e importado!', 'success');
            
            // Limpa o arquivo selecionado
            clearSelectedFile();
            // Atualiza metadados e gráficos
            fetchStatus();
            loadAmpereCompletoData();
        } else {
            appendLog(`[ERRO] Falha no ETL do PDF: ${res.message}`, 'error');
            showToast('Falha no Processamento', `Erro ao extrair dados do PDF: ${res.message}`, 'error');
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    } catch (error) {
        appendLog(`[ERRO] Falha de rede ao enviar PDF: ${error.message}`, 'error');
        showToast('Erro de Rede', 'Não foi possível conectar ao servidor para enviar o PDF.', 'error');
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

// ----------------- AUXILIARES DO CONSOLE DE LOGS -----------------
function appendLog(message, type = 'info') {
    const consoleLogs = document.getElementById('console-logs');
    if (!consoleLogs) return;
    
    const line = document.createElement('div');
    line.className = `log-line log-${type}`;
    line.textContent = `> ${message}`;
    consoleLogs.appendChild(line);
    
    // Auto-scroll no console
    consoleLogs.scrollTop = consoleLogs.scrollHeight;
}

function clearConsole() {
    const consoleLogs = document.getElementById('console-logs');
    if (consoleLogs) {
        consoleLogs.innerHTML = `<div class="log-line log-system">> Console limpo. Aguardando instrução...</div>`;
    }
}

// ----------------- TOAST NOTIFICATIONS -----------------
function showToast(title, message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    // Ícone correspondente
    let iconClass = 'fa-circle-info';
    if (type === 'success') iconClass = 'fa-circle-check';
    if (type === 'error') iconClass = 'fa-circle-exclamation';
    
    toast.innerHTML = `
        <i class="fa-solid ${iconClass} toast-icon"></i>
        <div class="toast-content">
            <div class="toast-title">${title}</div>
            <div class="toast-message">${message}</div>
        </div>
    `;
    
    container.appendChild(toast);
    
    // Trigger CSS animation
    setTimeout(() => toast.classList.add('show'), 10);
    
    // Auto remove após 4s
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// ----------------- AUXILIARES DE FORMATAÇÃO DE DATA -----------------
function formatDateString(dateStr) {
    // Transforma "YYYY-MM-DD" em "DD/MM/YYYY" ou similar curto sem desvio de timezone
    if (!dateStr) return '';
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return dateStr;
    
    if (/^\d{4}-\d{2}-\d{2}/.test(dateStr)) {
        const dia = String(date.getUTCDate()).padStart(2, '0');
        const mes = String(date.getUTCMonth() + 1).padStart(2, '0');
        return `${dia}/${mes}`;
    }
    
    const dia = String(date.getDate()).padStart(2, '0');
    const mes = String(date.getMonth() + 1).padStart(2, '0');
    return `${dia}/${mes}`;
}

function formatMonthYear(dateStr) {
    // Transforma "YYYY-MM-DD" em "MMM/YY" sem desvio de timezone
    if (!dateStr) return '';
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return dateStr;
    
    const meses = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];
    
    if (/^\d{4}-\d{2}-\d{2}/.test(dateStr)) {
        const mes = meses[date.getUTCMonth()];
        const ano = String(date.getUTCFullYear()).substring(2);
        return `${mes}/${ano}`;
    }
    
    const mes = meses[date.getMonth()];
    const ano = String(date.getFullYear()).substring(2);
    return `${mes}/${ano}`;
}

// Suporte para o javascript do string matching do final de arquivos em navegadores antigos
if (!String.prototype.endswith) {
    String.prototype.endswith = function(suffix) {
        return this.indexOf(suffix, this.length - suffix.length) !== -1;
    };
}

// ----------------- AUXILIARES PARA CÁLCULO DE MÍNIMO E MÁXIMO (COM HORAS) -----------------
function findMinMax(data, keyExtractor) {
    if (!data || data.length === 0) {
        return { min: 0, minTime: '--:--', max: 0, maxTime: '--:--' };
    }
    
    let minVal = Infinity;
    let minTime = '';
    let maxVal = -Infinity;
    let maxTime = '';
    
    data.forEach(d => {
        const val = keyExtractor(d);
        const time = d.din_instante.split(' ')[1]; // HH:MM
        
        if (val < minVal) {
            minVal = val;
            minTime = time;
        }
        if (val > maxVal) {
            maxVal = val;
            maxTime = time;
        }
    });
    
    return { min: minVal, minTime, max: maxVal, maxTime };
}

function updateMinMaxDOM(idSuffix, stats, prefix = '') {
    const elMin = document.getElementById(`${prefix}min-${idSuffix}`);
    const elMinTime = document.getElementById(`${prefix}min-time-${idSuffix}`);
    const elMax = document.getElementById(`${prefix}max-${idSuffix}`);
    const elMaxTime = document.getElementById(`${prefix}max-time-${idSuffix}`);
    
    if (elMin) elMin.textContent = formatNumber(stats.min, 0);
    if (elMinTime) elMinTime.textContent = `(${stats.minTime})`;
    if (elMax) elMax.textContent = formatNumber(stats.max, 0);
    if (elMaxTime) elMaxTime.textContent = `(${stats.maxTime})`;
}

// ----------------- LÓGICA DO MODO COMPARATIVO -----------------

function switchBalancoModo(modo) {
    currentBalancoModo = modo;
    
    const btnSimples = document.getElementById('subtab-balanco-simples');
    const btnComp = document.getElementById('subtab-balanco-comparacao');
    const painelSimples = document.getElementById('balanco-painel-simples');
    const painelComparacao = document.getElementById('balanco-painel-comparacao');
    
    if (btnSimples && btnComp && painelSimples && painelComparacao) {
        if (modo === 'simples') {
            btnSimples.classList.add('active');
            btnComp.classList.remove('active');
            painelSimples.style.display = 'block';
            painelComparacao.style.display = 'none';
            renderBalancoChart();
        } else {
            btnSimples.classList.remove('active');
            btnComp.classList.add('active');
            painelSimples.style.display = 'none';
            painelComparacao.style.display = 'block';
            renderBalancoComparison();
        }
    }
}

function renderBalancoComparison() {
    if (!rawBalancoData) return;
    
    const subA = document.getElementById('comp-a-sub-select').value;
    const dataA = document.getElementById('comp-a-data-input').value;
    const subB = document.getElementById('comp-b-sub-select').value;
    const dataB = document.getElementById('comp-b-data-input').value;
    
    if (!dataA || !dataB) return;
    
    // Atualiza tags de cabeçalho
    const tagA = document.getElementById('title-tag-a');
    const tagB = document.getElementById('title-tag-b');
    if (tagA) tagA.textContent = `${subA} - ${formatDateString(dataA)}`;
    if (tagB) tagB.textContent = `${subB} - ${formatDateString(dataB)}`;
    
    // --- CENÁRIO A ---
    let filteredA = rawBalancoData.filter(d => d.id_subsistema === subA && d.din_instante.startsWith(dataA));
    filteredA.sort((a, b) => a.din_instante.localeCompare(b.din_instante));
    
    const countA = filteredA.length;
    let sumHidA = 0, sumTerA = 0, sumEolA = 0, sumSolA = 0, sumCargaA = 0, sumInterA = 0;
    
    filteredA.forEach(d => {
        sumHidA += d.val_gerhidraulica || 0;
        sumTerA += d.val_gertermica || 0;
        sumEolA += d.val_gereolica || 0;
        sumSolA += d.val_gersolar || 0;
        sumCargaA += d.val_carga || 0;
        sumInterA += d.val_intercambio || 0;
    });
    
    const avgHidA = countA > 0 ? sumHidA / countA : 0;
    const avgTerA = countA > 0 ? sumTerA / countA : 0;
    const avgEolA = countA > 0 ? sumEolA / countA : 0;
    const avgSolA = countA > 0 ? sumSolA / countA : 0;
    const avgCargaA = countA > 0 ? sumCargaA / countA : 0;
    const avgInterA = countA > 0 ? sumInterA / countA : 0;
    const avgTotalGerA = avgHidA + avgTerA + avgEolA + avgSolA;
    
    // Atualiza cards Cenário A
    document.getElementById('comp-a-avg-geracao-total').textContent = formatNumber(avgTotalGerA, 0);
    document.getElementById('comp-a-avg-carga').textContent = formatNumber(avgCargaA, 0);
    document.getElementById('comp-a-avg-ger-hidraulica').textContent = formatNumber(avgHidA, 0);
    document.getElementById('comp-a-avg-ger-termica').textContent = formatNumber(avgTerA, 0);
    document.getElementById('comp-a-avg-ger-eolica').textContent = formatNumber(avgEolA, 0);
    document.getElementById('comp-a-avg-ger-solar').textContent = formatNumber(avgSolA, 0);
    document.getElementById('comp-a-avg-intercambio').textContent = formatNumber(avgInterA, 0);
    
    // Atualiza card PLD Cenário A
    const submercadoA = getSubmercadoBySubsistema(subA);
    const avgPldA = calculateAvgPld(submercadoA, dataA);
    const elAvgPldA = document.getElementById('comp-a-avg-pld-diario');
    if (elAvgPldA) {
        if (avgPldA !== null) {
            elAvgPldA.textContent = `R$ ${formatNumber(avgPldA, 0)}`;
        } else {
            elAvgPldA.textContent = '-';
        }
    }
    renderPldStrip('pld-strip-comp-a', 'pld-strip-grid-comp-a', submercadoA, dataA);
    
    // Extremos Cenário A
    const extTotalGer = d => (d.val_gerhidraulica || 0) + (d.val_gertermica || 0) + (d.val_gereolica || 0) + (d.val_gersolar || 0);
    updateMinMaxDOM('geracao-total', findMinMax(filteredA, extTotalGer), 'comp-a-');
    updateMinMaxDOM('carga', findMinMax(filteredA, d => d.val_carga || 0), 'comp-a-');
    updateMinMaxDOM('ger-hidraulica', findMinMax(filteredA, d => d.val_gerhidraulica || 0), 'comp-a-');
    updateMinMaxDOM('ger-termica', findMinMax(filteredA, d => d.val_gertermica || 0), 'comp-a-');
    updateMinMaxDOM('ger-eolica', findMinMax(filteredA, d => d.val_gereolica || 0), 'comp-a-');
    updateMinMaxDOM('ger-solar', findMinMax(filteredA, d => d.val_gersolar || 0), 'comp-a-');
    updateMinMaxDOM('intercambio', findMinMax(filteredA, d => d.val_intercambio || 0), 'comp-a-');
    
    // Gráfico Cenário A
    plotComparisonChart('chart-balanco-comp-a', 'balancoCompA', filteredA);
    
    // --- CENÁRIO B ---
    let filteredB = rawBalancoData.filter(d => d.id_subsistema === subB && d.din_instante.startsWith(dataB));
    filteredB.sort((a, b) => a.din_instante.localeCompare(b.din_instante));
    
    const countB = filteredB.length;
    let sumHidB = 0, sumTerB = 0, sumEolB = 0, sumSolB = 0, sumCargaB = 0, sumInterB = 0;
    
    filteredB.forEach(d => {
        sumHidB += d.val_gerhidraulica || 0;
        sumTerB += d.val_gertermica || 0;
        sumEolB += d.val_gereolica || 0;
        sumSolB += d.val_gersolar || 0;
        sumCargaB += d.val_carga || 0;
        sumInterB += d.val_intercambio || 0;
    });
    
    const avgHidB = countB > 0 ? sumHidB / countB : 0;
    const avgTerB = countB > 0 ? sumTerB / countB : 0;
    const avgEolB = countB > 0 ? sumEolB / countB : 0;
    const avgSolB = countB > 0 ? sumSolB / countB : 0;
    const avgCargaB = countB > 0 ? sumCargaB / countB : 0;
    const avgInterB = countB > 0 ? sumInterB / countB : 0;
    const avgTotalGerB = avgHidB + avgTerB + avgEolB + avgSolB;
    
    // Atualiza cards Cenário B
    document.getElementById('comp-b-avg-geracao-total').textContent = formatNumber(avgTotalGerB, 0);
    document.getElementById('comp-b-avg-carga').textContent = formatNumber(avgCargaB, 0);
    document.getElementById('comp-b-avg-ger-hidraulica').textContent = formatNumber(avgHidB, 0);
    document.getElementById('comp-b-avg-ger-termica').textContent = formatNumber(avgTerB, 0);
    document.getElementById('comp-b-avg-ger-eolica').textContent = formatNumber(avgEolB, 0);
    document.getElementById('comp-b-avg-ger-solar').textContent = formatNumber(avgSolB, 0);
    document.getElementById('comp-b-avg-intercambio').textContent = formatNumber(avgInterB, 0);
    
    // Atualiza card PLD Cenário B
    const submercadoB = getSubmercadoBySubsistema(subB);
    const avgPldB = calculateAvgPld(submercadoB, dataB);
    const elAvgPldB = document.getElementById('comp-b-avg-pld-diario');
    if (elAvgPldB) {
        if (avgPldB !== null) {
            elAvgPldB.textContent = `R$ ${formatNumber(avgPldB, 0)}`;
        } else {
            elAvgPldB.textContent = '-';
        }
    }
    renderPldStrip('pld-strip-comp-b', 'pld-strip-grid-comp-b', submercadoB, dataB);
    
    // Extremos Cenário B
    updateMinMaxDOM('geracao-total', findMinMax(filteredB, extTotalGer), 'comp-b-');
    updateMinMaxDOM('carga', findMinMax(filteredB, d => d.val_carga || 0), 'comp-b-');
    updateMinMaxDOM('ger-hidraulica', findMinMax(filteredB, d => d.val_gerhidraulica || 0), 'comp-b-');
    updateMinMaxDOM('ger-termica', findMinMax(filteredB, d => d.val_gertermica || 0), 'comp-b-');
    updateMinMaxDOM('ger-eolica', findMinMax(filteredB, d => d.val_gereolica || 0), 'comp-b-');
    updateMinMaxDOM('ger-solar', findMinMax(filteredB, d => d.val_gersolar || 0), 'comp-b-');
    updateMinMaxDOM('intercambio', findMinMax(filteredB, d => d.val_intercambio || 0), 'comp-b-');
    
    // Gráfico Cenário B
    plotComparisonChart('chart-balanco-comp-b', 'balancoCompB', filteredB);
    
    // --- DELTAS (VARIAÇÃO: B vs A) ---
    // Carga Delta
    const diffCarga = avgCargaB - avgCargaA;
    const pctCarga = avgCargaA !== 0 ? (diffCarga / avgCargaA) * 100 : 0;
    
    // Geração Delta
    const diffGer = avgTotalGerB - avgTotalGerA;
    const pctGer = avgTotalGerA !== 0 ? (diffGer / avgTotalGerA) * 100 : 0;
    
    // Atualiza painel DOM de Deltas
    updateDeltaUI('carga', diffCarga, pctCarga);
    updateDeltaUI('geracao', diffGer, pctGer);
}

function updateDeltaUI(type, diff, pct) {
    const elAbs = document.getElementById(`delta-val-abs-${type}`);
    const elPct = document.getElementById(`delta-val-pct-${type}`);
    const elItem = document.getElementById(`delta-item-${type}`);
    
    if (!elAbs || !elPct || !elItem) return;
    
    const diffStr = diff > 0 ? `+${formatNumber(diff, 0)}` : formatNumber(diff, 0);
    const pctStr = pct > 0 ? `+${formatNumber(pct, 1)}%` : `${formatNumber(pct, 1)}%`;
    
    elAbs.textContent = `${diffStr} MWm`;
    elPct.textContent = pctStr;
    
    // Reseta classes
    elItem.classList.remove('delta-up', 'delta-down', 'delta-neutral');
    
    if (diff > 0.5) {
        elItem.classList.add('delta-up');
    } else if (diff < -0.5) {
        elItem.classList.add('delta-down');
    } else {
        elItem.classList.add('delta-neutral');
        elAbs.textContent = `0 MWm`;
        elPct.textContent = `0.0%`;
    }
}

function plotComparisonChart(canvasId, chartKey, filteredData) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    
    if (charts[chartKey]) {
        charts[chartKey].destroy();
    }
    
    const labels = filteredData.map(d => d.din_instante.split(' ')[1]);
    const gerHidraulica = filteredData.map(d => d.val_gerhidraulica || 0);
    const gerTermica = filteredData.map(d => d.val_gertermica || 0);
    const gerEolica = filteredData.map(d => d.val_gereolica || 0);
    const gerSolar = filteredData.map(d => d.val_gersolar || 0);
    const carga = filteredData.map(d => d.val_carga || 0);
    
    charts[chartKey] = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Carga Total',
                    data: carga,
                    borderColor: '#f43f5e',
                    borderWidth: 2.5,
                    pointRadius: 0.5,
                    pointHoverRadius: 3,
                    fill: false,
                    tension: 0.15,
                    stack: 'carga',
                    order: 0
                },
                {
                    label: 'Geração Térmica',
                    data: gerTermica,
                    borderColor: '#f97316',
                    backgroundColor: 'rgba(249, 115, 22, 0.08)',
                    borderWidth: 1,
                    pointRadius: 0,
                    pointHoverRadius: 2,
                    fill: true,
                    stack: 'geracao',
                    order: 1
                },
                {
                    label: 'Geração Solar',
                    data: gerSolar,
                    borderColor: '#eab308',
                    backgroundColor: 'rgba(234, 179, 8, 0.08)',
                    borderWidth: 1,
                    pointRadius: 0,
                    pointHoverRadius: 2,
                    fill: true,
                    stack: 'geracao',
                    order: 2
                },
                {
                    label: 'Geração Hidráulica',
                    data: gerHidraulica,
                    borderColor: '#38bdf8',
                    backgroundColor: 'rgba(56, 189, 248, 0.08)',
                    borderWidth: 1,
                    pointRadius: 0,
                    pointHoverRadius: 2,
                    fill: true,
                    stack: 'geracao',
                    order: 3
                },
                {
                    label: 'Geração Eólica',
                    data: gerEolica,
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.08)',
                    borderWidth: 1,
                    pointRadius: 0,
                    pointHoverRadius: 2,
                    fill: true,
                    stack: 'geracao',
                    order: 4
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.03)' },
                    ticks: { color: '#94a3b8', font: { size: 9 } }
                },
                y: {
                    stacked: true,
                    grid: { color: 'rgba(255, 255, 255, 0.03)' },
                    ticks: { color: '#94a3b8', font: { size: 9 } }
                }
            },
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#f8fafc', font: { family: 'Inter', size: 9 }, boxWidth: 12 }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false
                }
            }
        }
    });
}

// ----------------- AUXILIARES DO PLD HORÁRIO NO BALANÇO ONS -----------------
function getSubmercadoBySubsistema(sub) {
    const mapping = {
        'SE': 'SUDESTE',
        'S': 'SUL',
        'NE': 'NORDESTE',
        'N': 'NORTE'
    };
    return mapping[sub] || null;
}

function calculateAvgPld(submercado, dataSelecionada) {
    if (!submercado || !rawPldHorarioData || !rawPldHorarioData[dataSelecionada] || !rawPldHorarioData[dataSelecionada][submercado]) {
        return null;
    }
    const pldValores = rawPldHorarioData[dataSelecionada][submercado];
    if (!pldValores || pldValores.length === 0) return null;
    
    let sum = 0;
    let count = 0;
    pldValores.forEach(v => {
        if (v !== null && v !== undefined) {
            sum += v;
            count++;
        }
    });
    return count > 0 ? sum / count : null;
}

function renderPldStrip(containerId, gridId, submercado, dataSelecionada) {
    const container = document.getElementById(containerId);
    const grid = document.getElementById(gridId);
    if (!container || !grid) return;
    
    if (!submercado || !rawPldHorarioData || !rawPldHorarioData[dataSelecionada] || !rawPldHorarioData[dataSelecionada][submercado]) {
        container.style.display = 'none';
        return;
    }
    
    const pldValores = rawPldHorarioData[dataSelecionada][submercado];
    
    // Calcula os valores mínimo e máximo do dia para o gradiente de cores
    const nonNullVals = pldValores.filter(v => v !== null && v !== undefined);
    const minVal = nonNullVals.length > 0 ? Math.min(...nonNullVals) : 0;
    const maxVal = nonNullVals.length > 0 ? Math.max(...nonNullVals) : 0;
    
    let gridHtml = '';
    for (let hora = 0; hora < 24; hora++) {
        const val = pldValores[hora] !== undefined ? pldValores[hora] : null;
        let displayVal = '-';
        let styleAttr = '';
        
        if (val !== null) {
            const roundedVal = Math.round(val);
            displayVal = `R$ ${roundedVal}`;
            
            if (maxVal === minVal) {
                // Caso todos os valores sejam iguais, aplica uma cor verde neutra
                styleAttr = `style="color: hsl(140, 70%, 60%);"`;
            } else {
                // Calcula a posição do valor atual na escala (0 a 1)
                const t = (val - minVal) / (maxVal - minVal);
                // Interpola a matiz (hue) de 140 (verde esmeralda) a 10 (vermelho quente)
                const h = 140 - (t * 130);
                styleAttr = `style="color: hsl(${h}, 70%, 55%);"`;
            }
        }
        
        const horaStr = String(hora).padStart(2, '0') + ':00';
        gridHtml += `
            <div class="pld-strip-cell">
                <span class="pld-cell-hour">${horaStr}</span>
                <span class="pld-cell-val" ${styleAttr}>${displayVal}</span>
            </div>
        `;
    }
    
    grid.innerHTML = gridHtml;
    container.style.display = 'block';
}

// ----------------- HISTÓRICO BBCE -----------------
let selectedBbceProducts = [];

async function loadBbceData() {
    try {
        const response = await fetch('/api/data/bbce');
        if (response.ok) {
            rawBbceData = await response.json();
            
            // Inicializa seletores de data da BBCE
            if (rawBbceData && rawBbceData.length > 0) {
                const datasUnicas = [...new Set(rawBbceData.map(d => d.DATA_DIA))].sort();
                
                const inputInicio = document.getElementById('bbce-data-inicio');
                const inputFim = document.getElementById('bbce-data-fim');
                
                if (inputInicio && inputFim) {
                    const maxData = datasUnicas[datasUnicas.length - 1];
                    inputFim.value = maxData;
                    inputFim.max = maxData;
                    inputFim.min = datasUnicas[0];
                    
                    // Ajustado para 6 meses de intervalo padrão
                    const dataFimObj = new Date(maxData + 'T12:00:00');
                    const dataInicioObj = new Date(dataFimObj);
                    dataInicioObj.setMonth(dataInicioObj.getMonth() - 6);
                    const dataInicioStr = dataInicioObj.toISOString().split('T')[0];
                    
                    inputInicio.value = dataInicioStr < datasUnicas[0] ? datasUnicas[0] : dataInicioStr;
                    inputInicio.max = maxData;
                    inputInicio.min = datasUnicas[0];

                    // Inicializa o Double Range Slider
                    initBbceRangeSlider(datasUnicas);
                }
            }
            
            // Extrai produtos únicos e inicializa o autocompletar
            let uniqueProducts = [];
            if (rawBbceData && rawBbceData.length > 0) {
                const prodsSet = new Set(rawBbceData.map(d => d.PRODUTO).filter(p => p));
                uniqueProducts = [...prodsSet].sort();
            }
            initBbceAutocomplete(uniqueProducts);
            
            renderBbceChart();
        }
    } catch (error) {
        console.error("Erro ao carregar dados da BBCE:", error);
    }
}

function initBbceAutocomplete(products) {
    const input = document.getElementById('bbce-produto-search');
    const dropdown = document.getElementById('bbce-autocomplete-list');
    
    if (!input || !dropdown) return;
    
    // Configura evento de digitação
    input.addEventListener('input', () => {
        const query = input.value.trim().toUpperCase();
        if (!query) {
            dropdown.style.display = 'none';
            return;
        }
        
        // Filtra produtos que contêm a query e que ainda não estão selecionados
        const filtered = products.filter(p => 
            p.toUpperCase().includes(query) && 
            !selectedBbceProducts.includes(p)
        ).slice(0, 10);
        
        if (filtered.length === 0) {
            dropdown.innerHTML = '<div class="autocomplete-item" style="color: var(--text-muted); cursor: default;">Nenhum produto encontrado</div>';
        } else {
            let html = '';
            filtered.forEach(p => {
                html += `<div class="autocomplete-item" data-value="${p}">${p}</div>`;
            });
            dropdown.innerHTML = html;
            
            dropdown.querySelectorAll('.autocomplete-item').forEach(item => {
                item.addEventListener('click', () => {
                    const val = item.getAttribute('data-value');
                    addBbceProductChip(val);
                    input.value = '';
                    dropdown.style.display = 'none';
                });
            });
        }
        dropdown.style.display = 'block';
    });
    
    // Fecha dropdown ao clicar fora
    document.addEventListener('click', (e) => {
        if (e.target !== input && e.target !== dropdown) {
            dropdown.style.display = 'none';
        }
    });
    
    // Garante que, ao carregar a página pela primeira vez, tenhamos produtos pré-selecionados
    if (selectedBbceProducts.length === 0 && products.length > 0) {
        // Encontra a data máxima na base de dados
        let maxDateStr = "";
        rawBbceData.forEach(d => {
            if (d.DATA_DIA && d.DATA_DIA > maxDateStr) {
                maxDateStr = d.DATA_DIA;
            }
        });
        
        // Calcula a data limite de 3 meses atrás
        let limitDateStr = "";
        if (maxDateStr) {
            const maxDate = new Date(maxDateStr + 'T12:00:00');
            const threeMonthsAgo = new Date(maxDate);
            threeMonthsAgo.setMonth(threeMonthsAgo.getMonth() - 3);
            limitDateStr = threeMonthsAgo.toISOString().split('T')[0];
        }

        // Seleciona os top 3 produtos com mais negócios nos últimos 3 meses
        let countMap = {};
        rawBbceData.forEach(d => {
            if (d.PRODUTO && (!limitDateStr || d.DATA_DIA >= limitDateStr)) {
                countMap[d.PRODUTO] = (countMap[d.PRODUTO] || 0) + (d.total_contratos || 1);
            }
        });
        
        // Fallback: se nenhum produto foi encontrado no período (ex: base sem dados nos últimos 3 meses), considera toda a base
        if (Object.keys(countMap).length === 0) {
            rawBbceData.forEach(d => {
                if (d.PRODUTO) {
                    countMap[d.PRODUTO] = (countMap[d.PRODUTO] || 0) + (d.total_contratos || 1);
                }
            });
        }
        
        const sortedProductsByCount = Object.keys(countMap).sort((a, b) => countMap[b] - countMap[a]);
        const defaultSelection = sortedProductsByCount.slice(0, 3);
        
        defaultSelection.forEach(p => {
            selectedBbceProducts.push(p);
        });
        
        renderBbceChips();
    }
}

function initBbceRangeSlider(datasUnicas) {
    const minRange = document.getElementById('bbce-range-min');
    const maxRange = document.getElementById('bbce-range-max');
    const highlight = document.getElementById('bbce-range-highlight');
    const inputInicio = document.getElementById('bbce-data-inicio');
    const inputFim = document.getElementById('bbce-data-fim');
    
    if (!minRange || !maxRange || !highlight || !inputInicio || !inputFim) return;
    
    const total = datasUnicas.length - 1;
    minRange.min = 0;
    minRange.max = total;
    maxRange.min = 0;
    maxRange.max = total;
    
    // Define posições iniciais dos sliders com base nos inputs carregados
    let startIdx = datasUnicas.indexOf(inputInicio.value);
    let endIdx = datasUnicas.indexOf(inputFim.value);
    if (startIdx === -1) startIdx = 0;
    if (endIdx === -1) endIdx = total;
    
    minRange.value = startIdx;
    maxRange.value = endIdx;
    
    const updateSliderHighlight = () => {
        const minVal = parseInt(minRange.value);
        const maxVal = parseInt(maxRange.value);
        
        const percentMin = total > 0 ? (minVal / total) * 100 : 0;
        const percentMax = total > 0 ? (maxVal / total) * 100 : 0;
        
        highlight.style.left = percentMin + '%';
        highlight.style.width = (percentMax - percentMin) + '%';
    };
    
    // Listener para slider de data início
    minRange.addEventListener('input', () => {
        let minVal = parseInt(minRange.value);
        let maxVal = parseInt(maxRange.value);
        
        // Garante que o mínimo não sobreponha ou ultrapasse o máximo
        if (minVal >= maxVal) {
            minRange.value = maxVal - 1;
            minVal = maxVal - 1;
        }
        
        inputInicio.value = datasUnicas[minVal];
        updateSliderHighlight();
        renderBbceChart();
    });
    
    // Listener para slider de data fim
    maxRange.addEventListener('input', () => {
        let minVal = parseInt(minRange.value);
        let maxVal = parseInt(maxRange.value);
        
        // Garante que o máximo não seja menor ou igual ao mínimo
        if (maxVal <= minVal) {
            maxRange.value = minVal + 1;
            maxVal = minVal + 1;
        }
        
        inputFim.value = datasUnicas[maxVal];
        updateSliderHighlight();
        renderBbceChart();
    });
    
    // Sincroniza sliders caso as datas sejam editadas manualmente/selecionadas nos inputs
    inputInicio.addEventListener('change', () => {
        let idx = datasUnicas.indexOf(inputInicio.value);
        if (idx !== -1) {
            let maxVal = parseInt(maxRange.value);
            if (idx >= maxVal) {
                idx = maxVal - 1;
                inputInicio.value = datasUnicas[idx];
            }
            minRange.value = idx;
            updateSliderHighlight();
            renderBbceChart();
        }
    });
    
    inputFim.addEventListener('change', () => {
        let idx = datasUnicas.indexOf(inputFim.value);
        if (idx !== -1) {
            let minVal = parseInt(minRange.value);
            if (idx <= minVal) {
                idx = minVal + 1;
                inputFim.value = datasUnicas[idx];
            }
            maxRange.value = idx;
            updateSliderHighlight();
            renderBbceChart();
        }
    });
    
    // Inicializa a pintura da track ativa
    updateSliderHighlight();
}

function addBbceProductChip(productName) {
    if (!productName || selectedBbceProducts.includes(productName)) return;
    selectedBbceProducts.push(productName);
    renderBbceChips();
    renderBbceChart();
}

function removeBbceProductChip(productName) {
    selectedBbceProducts = selectedBbceProducts.filter(p => p !== productName);
    renderBbceChips();
    renderBbceChart();
}

function renderBbceChips() {
    const container = document.getElementById('bbce-selected-chips');
    if (!container) return;
    
    container.innerHTML = `<span style="font-size: 11px; color: var(--text-secondary); margin-right: 8px;"><i class="fa-solid fa-tags"></i> Selecionados:</span>`;
    
    if (selectedBbceProducts.length === 0) {
        container.innerHTML += `<span style="font-size: 11px; color: var(--text-muted); font-style: italic;">Nenhum produto selecionado. Busque produtos acima para plotar.</span>`;
        return;
    }
    
    selectedBbceProducts.forEach(prod => {
        const chip = document.createElement('div');
        chip.className = 'product-chip';
        chip.innerHTML = `
            <span>${prod}</span>
            <span class="product-chip-remove" data-value="${prod}">&times;</span>
        `;
        container.appendChild(chip);
    });
    
    container.querySelectorAll('.product-chip-remove').forEach(btn => {
        btn.addEventListener('click', () => {
            const val = btn.getAttribute('data-value');
            removeBbceProductChip(val);
        });
    });
}

function renderBbceChart() {
    const contrato = document.getElementById('bbce-contrato-select').value;
    const dataInicio = document.getElementById('bbce-data-inicio').value;
    const dataFim = document.getElementById('bbce-data-fim').value;
    const canvas = document.getElementById('chart-bbce-historico');
    
    if (!canvas || !rawBbceData) return;
    
    if (selectedBbceProducts.length === 0) {
        document.getElementById('bbce-metric-preco-medio').textContent = '-';
        document.getElementById('bbce-metric-volume').textContent = '-';
        document.getElementById('bbce-metric-contratos').textContent = '-';
        
        const elMin = document.getElementById('bbce-preco-min');
        const elMinTime = document.getElementById('bbce-time-preco-min');
        const elMax = document.getElementById('bbce-preco-max');
        const elMaxTime = document.getElementById('bbce-time-preco-max');
        if (elMin) elMin.textContent = '-';
        if (elMinTime) elMinTime.textContent = '(--/--)';
        if (elMax) elMax.textContent = '-';
        if (elMaxTime) elMaxTime.textContent = '(--/--)';
        
        if (charts.bbce) {
            charts.bbce.destroy();
            charts.bbce = null;
        }
        return;
    }
    
    // 1. Filtragem básica (datas e contrato)
    let filtrados = rawBbceData;
    if (contrato !== 'Todos') {
        filtrados = filtrados.filter(d => d['TIPO DE CONTRATO'] === contrato);
    }
    if (dataInicio) {
        filtrados = filtrados.filter(d => d.DATA_DIA >= dataInicio);
    }
    if (dataFim) {
        filtrados = filtrados.filter(d => d.DATA_DIA <= dataFim);
    }
    
    // Filtra pelos produtos selecionados
    filtrados = filtrados.filter(d => selectedBbceProducts.includes(d.PRODUTO));
    
    // 2. Coleta dias únicos ordenados
    const diasUnicos = [...new Set(filtrados.map(d => d.DATA_DIA))].sort();
    
    const dadosEstruturados = {};
    diasUnicos.forEach(dia => {
        dadosEstruturados[dia] = {};
        selectedBbceProducts.forEach(prod => {
            dadosEstruturados[dia][prod] = { preco: null, volume: 0, contratos: 0 };
        });
    });
    
    filtrados.forEach(row => {
        const dia = row.DATA_DIA;
        const prod = row.PRODUTO;
        const vol = parseFloat(row.VOLUME_TOTAL) || 0;
        const preco = parseFloat(row.PRECO_MEDIO) || 0;
        const contr = parseInt(row.total_contratos) || 0;
        
        if (dadosEstruturados[dia] && dadosEstruturados[dia][prod]) {
            dadosEstruturados[dia][prod].preco = preco;
            dadosEstruturados[dia][prod].volume = vol;
            dadosEstruturados[dia][prod].contratos = contr;
        }
    });
    
    const labels = diasUnicos.map(dia => {
        const partes = dia.split('-');
        return `${partes[2]}/${partes[1]}`;
    });
    
    const colorPalette = ['#10b981', '#3b82f6', '#f59e0b', '#a855f7', '#f43f5e', '#06b6d4', '#eab308', '#ec4899'];
    const datasets = [];
    
    selectedBbceProducts.forEach((prod, idx) => {
        const precosProd = diasUnicos.map(dia => dadosEstruturados[dia][prod].preco);
        
        datasets.push({
            type: 'line',
            label: `Preço: ${prod}`,
            data: precosProd,
            borderColor: colorPalette[idx % colorPalette.length],
            backgroundColor: 'transparent',
            borderWidth: 2.5,
            tension: 0.1,
            pointRadius: diasUnicos.length > 50 ? 0 : 3,
            pointHoverRadius: 6,
            yAxisID: 'yPrice',
            spanGaps: true
        });
    });
    
    const volumesConsolidados = diasUnicos.map(dia => {
        let somaVol = 0;
        selectedBbceProducts.forEach(prod => {
            somaVol += dadosEstruturados[dia][prod].volume;
        });
        return parseFloat(somaVol.toFixed(2));
    });
    
    datasets.push({
        type: 'bar',
        label: 'Volume Total Consolidado (MWm)',
        data: volumesConsolidados,
        backgroundColor: 'rgba(255, 255, 255, 0.05)',
        borderColor: 'rgba(255, 255, 255, 0.12)',
        borderWidth: 1,
        barPercentage: 0.7,
        yAxisID: 'yVolume'
    });
    
    let totalVolumePeriodo = 0;
    let totalContratosPeriodo = 0;
    let somaPrecoVolPeriodo = 0;
    
    let precoMin = Infinity;
    let dataMin = '';
    let precoMax = -Infinity;
    let dataMax = '';
    
    filtrados.forEach(row => {
        const vol = parseFloat(row.VOLUME_TOTAL) || 0;
        const preco = parseFloat(row.PRECO_MEDIO) || 0;
        const contr = parseInt(row.total_contratos) || 0;
        const dia = row.DATA_DIA;
        
        totalVolumePeriodo += vol;
        totalContratosPeriodo += contr;
        somaPrecoVolPeriodo += (preco * vol);
        
        if (preco > 0) {
            if (preco < precoMin) {
                precoMin = preco;
                dataMin = dia;
            }
            if (preco > precoMax) {
                precoMax = preco;
                dataMax = dia;
            }
        }
    });
    
    const precoMedioPeriodo = totalVolumePeriodo > 0 ? (somaPrecoVolPeriodo / totalVolumePeriodo) : 0;
    
    document.getElementById('bbce-metric-preco-medio').textContent = precoMedioPeriodo > 0 ? 'R$ ' + formatNumber(precoMedioPeriodo, 2) : '-';
    document.getElementById('bbce-metric-volume').textContent = totalVolumePeriodo > 0 ? formatNumber(totalVolumePeriodo, 2) : '-';
    document.getElementById('bbce-metric-contratos').textContent = totalContratosPeriodo > 0 ? totalContratosPeriodo.toLocaleString('pt-BR') : '-';
    
    // Atualiza preço mínimo e máximo na interface
    const elMin = document.getElementById('bbce-preco-min');
    const elMinTime = document.getElementById('bbce-time-preco-min');
    const elMax = document.getElementById('bbce-preco-max');
    const elMaxTime = document.getElementById('bbce-time-preco-max');
    
    if (elMin && elMinTime && elMax && elMaxTime) {
        if (precoMin !== Infinity && precoMax !== -Infinity) {
            elMin.textContent = 'R$ ' + formatNumber(precoMin, 2);
            elMinTime.textContent = `(${formatDateString(dataMin)})`;
            elMax.textContent = 'R$ ' + formatNumber(precoMax, 2);
            elMaxTime.textContent = `(${formatDateString(dataMax)})`;
        } else {
            elMin.textContent = '-';
            elMinTime.textContent = '(--/--)';
            elMax.textContent = '-';
            elMaxTime.textContent = '(--/--)';
        }
    }
    
    if (charts.bbce) {
        charts.bbce.destroy();
    }
    
    charts.bbce = new Chart(canvas.getContext('2d'), {
        data: {
            labels: labels,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        color: '#a1a1aa',
                        font: { family: 'Inter', size: 10 },
                        boxWidth: 12
                    }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: '#18181b',
                    titleColor: '#f4f4f5',
                    bodyColor: '#a1a1aa',
                    borderColor: '#27272a',
                    borderWidth: 1,
                    titleFont: { family: 'Inter', weight: 'bold' },
                    bodyFont: { family: 'Inter' }
                }
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: {
                        color: '#71717a',
                        font: { family: 'Inter', size: 10 },
                        maxTicksLimit: 20
                    }
                },
                yPrice: {
                    type: 'linear',
                    position: 'left',
                    title: {
                        display: true,
                        text: 'Preço (R$/MWh)',
                        color: '#a1a1aa',
                        font: { family: 'Inter', size: 11, weight: 'bold' }
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)',
                        drawTicks: false
                    },
                    ticks: {
                        color: '#71717a',
                        font: { family: 'Inter', size: 10 }
                    }
                },
                yVolume: {
                    type: 'linear',
                    position: 'right',
                    title: {
                        display: true,
                        text: 'Volume Consolidado (MWm)',
                        color: '#a1a1aa',
                        font: { family: 'Inter', size: 11, weight: 'bold' }
                    },
                    grid: { display: false },
                    ticks: {
                        color: '#71717a',
                        font: { family: 'Inter', size: 10 }
                    }
                }
            }
        }
    });
}

// ----------------- DRAG AND DROP & UPLOAD MANUAL BBCE -----------------
let bbceFileToUpload = null;

function initDragAndDropBbce() {
    const dropzone = document.getElementById('bbce-dropzone');
    const fileInput = document.getElementById('bbce-file-input');
    
    if (!dropzone || !fileInput) return;
    
    dropzone.addEventListener('click', () => fileInput.click());
    
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleBbceFileSelection(e.target.files[0]);
        }
    });
    
    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.style.borderColor = 'var(--color-green)';
        dropzone.style.background = 'rgba(16, 185, 129, 0.03)';
    });
    
    dropzone.addEventListener('dragleave', () => {
        dropzone.style.borderColor = 'rgba(255, 255, 255, 0.15)';
        dropzone.style.background = 'transparent';
    });
    
    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.style.borderColor = 'rgba(255, 255, 255, 0.15)';
        dropzone.style.background = 'transparent';
        
        if (e.dataTransfer.files.length > 0) {
            handleBbceFileSelection(e.dataTransfer.files[0]);
        }
    });
}

function handleBbceFileSelection(file) {
    const ext = file.name.split('.').pop().toLowerCase();
    if (ext !== 'xlsx' && ext !== 'xls') {
        showToast('Formato Inválido', 'A planilha de negócios deve ser do tipo Excel (.xlsx ou .xls).', 'error');
        return;
    }
    
    bbceFileToUpload = file;
    document.getElementById('bbce-selected-file-name').textContent = file.name;
    document.getElementById('bbce-dropzone').style.display = 'none';
    document.getElementById('bbce-selected-file-area').style.display = 'block';
}

function clearSelectedBbceFile() {
    bbceFileToUpload = null;
    document.getElementById('bbce-file-input').value = '';
    document.getElementById('bbce-dropzone').style.display = 'block';
    document.getElementById('bbce-selected-file-area').style.display = 'none';
}

async function uploadBbceExcel() {
    if (!bbceFileToUpload) return;
    
    const btn = document.getElementById('btn-upload-bbce');
    const originalText = btn.innerHTML;
    
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Processando...';
    
    clearConsole();
    appendLog("Iniciando upload e processamento manual de negócios da BBCE...", "system");
    appendLog(`Arquivo selecionado: ${bbceFileToUpload.name} (${(bbceFileToUpload.size / 1024).toFixed(1)} KB)`, "info");
    
    const formData = new FormData();
    formData.append('file', bbceFileToUpload);
    
    try {
        const response = await fetch('/api/update/bbce_upload', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success) {
            appendLog(`Sucesso! Planilha BBCE processada de forma incremental.`, "success");
            appendLog(`Novos registros desduplicados inseridos: ${result.novos_registros}`, "success");
            appendLog(`Total de registros na base agora: ${result.total_registros}`, "info");
            
            showToast('Atualização Concluída', `Base BBCE atualizada com sucesso! +${result.novos_registros} linhas.`, 'success');
            clearSelectedBbceFile();
            
            fetchStatus();
            loadDashboardData();
        } else {
            throw new Error(result.message);
        }
    } catch (error) {
        appendLog(`ERRO: Falha ao processar arquivo BBCE: ${error.message}`, "error");
        showToast('Erro de Importação', error.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

// ----------------- AUTOMACAO SELENIUM BBCE -----------------
let bbceAutoInterval = null;

async function iniciarAutomacaoBBCE() {
    const btn = document.getElementById('btn-sync-bbce-auto');
    const originalText = btn.innerHTML;
    
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Inicializando...';
    
    clearConsole();
    appendLog("Calculando período de atualização necessário com base no último registro...", "system");
    
    try {
        const responseUltimo = await fetch('/api/bbce/ultimo_registro');
        const dataUltimo = await responseUltimo.json();
        
        let dataInicioStr = "";
        let dataFimStr = "";
        
        if (dataUltimo.max_data && dataUltimo.max_data.includes('/')) {
            appendLog(`Último negócio na base local: ${dataUltimo.max_data}`, "info");
            
            const diaStr = dataUltimo.max_data.split(' ')[0];
            const partes = diaStr.split('/');
            
            const dataBase = new Date(parseInt(partes[2]), parseInt(partes[1]) - 1, parseInt(partes[0]));
            dataBase.setDate(dataBase.getDate() + 1);
            
            const d = String(dataBase.getDate()).padStart(2, '0');
            const m = String(dataBase.getMonth() + 1).padStart(2, '0');
            const a = dataBase.getFullYear();
            dataInicioStr = `${d}/${m}/${a}`;
        } else {
            const dataBase = new Date();
            dataBase.setDate(dataBase.getDate() - 30);
            const d = String(dataBase.getDate()).padStart(2, '0');
            const m = String(dataBase.getMonth() + 1).padStart(2, '0');
            const a = dataBase.getFullYear();
            dataInicioStr = `${d}/${m}/${a}`;
            appendLog("Último negócio não identificado. Buscando últimos 30 dias por padrão.", "warning");
        }
        
        const ontem = new Date();
        ontem.setDate(ontem.getDate() - 1);
        const d_f = String(ontem.getDate()).padStart(2, '0');
        const m_f = String(ontem.getMonth() + 1).padStart(2, '0');
        const a_f = ontem.getFullYear();
        dataFimStr = `${d_f}/${m_f}/${a_f}`;
        
        appendLog(`Período de consulta calculado: ${dataInicioStr} até ${dataFimStr}`, "info");
        
        btn.innerHTML = '<i class="fa-solid fa-robot"></i> Executando Robô...';
        
        const responseAuto = await fetch('/api/update/bbce_auto', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                data_inicio: dataInicioStr,
                data_fim: dataFimStr
            })
        });
        
        const result = await responseAuto.json();
        
        if (result.success) {
            if (bbceAutoInterval) clearInterval(bbceAutoInterval);
            bbceAutoInterval = setInterval(pollBbceAutomationLogs, 1500);
        } else {
            throw new Error(result.message);
        }
        
    } catch (error) {
        appendLog(`ERRO ao inicializar robô BBCE: ${error.message}`, "error");
        showToast('Erro do Robô', error.message, 'error');
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

async function pollBbceAutomationLogs() {
    try {
        const response = await fetch('/api/update/bbce_auto/logs');
        const data = await response.json();
        
        if (data.logs && data.logs.length > 0) {
            const consoleLogs = document.getElementById('console-logs');
            if (consoleLogs) {
                consoleLogs.innerHTML = '';
                
                let checkSuccess = false;
                let checkError = false;
                let errorMessage = '';
                
                data.logs.forEach(line => {
                    const div = document.createElement('div');
                    div.className = 'log-line';
                    
                    if (line.includes('[SUCCESS]')) {
                        div.className += ' log-success';
                        div.textContent = `> ${line.replace('[SUCCESS] ', '')}`;
                        checkSuccess = true;
                    } else if (line.includes('[ERROR]')) {
                        div.className += ' log-error';
                        div.textContent = `> ${line.replace('[ERROR] ', '')}`;
                        checkError = true;
                        errorMessage = line.replace('[ERROR] ', '');
                    } else if (line.includes('[STATUS]')) {
                        div.className += ' log-system';
                        div.textContent = `> ${line.replace('[STATUS] ', '')}`;
                    } else {
                        div.className += ' log-info';
                        div.textContent = `> ${line}`;
                    }
                    
                    consoleLogs.appendChild(div);
                });
                
                consoleLogs.scrollTop = consoleLogs.scrollHeight;
                
                if (checkSuccess || checkError) {
                    clearInterval(bbceAutoInterval);
                    bbceAutoInterval = null;
                    
                    const btn = document.getElementById('btn-sync-bbce-auto');
                    if (btn) {
                        btn.disabled = false;
                        btn.innerHTML = '<i class="fa-solid fa-play"></i> Iniciar Robô BBCE';
                    }
                    
                    if (checkSuccess) {
                        showToast('Importação Concluída', 'Robô finalizou com sucesso!', 'success');
                        fetchStatus();
                        loadDashboardData();
                    } else {
                        showToast('Falha na Importação', errorMessage || 'Ocorreu um erro na execução do robô.', 'error');
                    }
                }
            }
        }
    } catch (error) {
        console.error("Erro no polling de logs da BBCE:", error);
    }
}

// ----------------- COMPARATIVO DE ENA (PREVISTO VS REALIZADO) -----------------
function switchEnaModo(modo) {
    currentEnaModo = modo;
    
    const btnHistorico = document.getElementById('subtab-ena-historico');
    const btnComparativo = document.getElementById('subtab-ena-comparativo');
    const painelHistorico = document.getElementById('ena-painel-historico');
    const painelComparativo = document.getElementById('ena-painel-comparativo');
    
    if (btnHistorico && btnComparativo && painelHistorico && painelComparativo) {
        if (modo === 'historico') {
            btnHistorico.classList.add('active');
            btnComparativo.classList.remove('active');
            painelHistorico.style.display = 'block';
            painelComparativo.style.display = 'none';
            renderEnaCharts();
        } else {
            btnHistorico.classList.remove('active');
            btnComparativo.classList.add('active');
            painelHistorico.style.display = 'none';
            painelComparativo.style.display = 'block';
            loadEnaComparativoMeses();
        }
    }
}

let rawEnaComparativoData = null;

async function loadEnaComparativoMeses() {
    try {
        const select = document.getElementById('ena-comp-mes-select');
        if (!select) return;
        
        const response = await fetch('/api/data/ena_comparativo/meses');
        if (!response.ok) throw new Error('Falha ao buscar meses de comparação.');
        
        const meses = await response.json();
        
        if (meses && meses.length > 0) {
            let html = '';
            meses.forEach(m => {
                html += `<option value="${m.id}">${m.label}</option>`;
            });
            select.innerHTML = html;
            
            // Dispara carregamento dos dados para o primeiro mês
            loadEnaComparativoData();
        } else {
            select.innerHTML = '<option value="">Nenhum mês disponível</option>';
        }
    } catch (error) {
        console.error("Erro ao buscar meses de comparação da ENA:", error);
        showToast('Erro', 'Não foi possível carregar os meses de comparação da ENA.', 'error');
    }
}

async function loadEnaComparativoData() {
    try {
        const select = document.getElementById('ena-comp-mes-select');
        if (!select || !select.value) return;
        
        const mes = select.value;
        
        // Exibe spinner temporário nos canvas
        ['se', 's', 'ne', 'n'].forEach(sub => {
            const canvas = document.getElementById(`chart-ena-comp-${sub}`);
            if (canvas) {
                const ctx = canvas.getContext('2d');
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                ctx.font = '14px Inter, sans-serif';
                ctx.fillStyle = '#a1a1aa';
                ctx.textAlign = 'center';
                ctx.fillText('Carregando comparativo...', canvas.width / 2, canvas.height / 2);
            }
        });
        
        const response = await fetch(`/api/data/ena_comparativo?mes=${mes}`);
        if (!response.ok) throw new Error('Erro ao buscar dados do comparativo de ENA.');
        
        rawEnaComparativoData = await response.json();
        
        renderEnaComparativoCharts();
    } catch (error) {
        console.error("Erro ao carregar dados comparativos de ENA:", error);
        showToast('Erro de Carregamento', 'Falha ao buscar dados comparativos de ENA.', 'error');
    }
}

function renderEnaComparativoCharts() {
    if (!rawEnaComparativoData || !rawEnaComparativoData.dados) return;
    
    const variavelRealizado = document.getElementById('ena-comp-variavel-select').value; // 'armazenavel' ou 'bruta'
    const semanasInfo = rawEnaComparativoData.semanas_info;
    const dados = rawEnaComparativoData.dados;
    
    // Labels do Eixo X: "Semana 1\n(30/05 a 05/06)" etc.
    const labels = semanasInfo.map(sem => [sem.label, `(${sem.periodo})`]);
    
    const subsistemas = [
        { id: 'SE', chartId: 'chart-ena-comp-se', chartRef: 'enaCompSE', tableId: 'table-ena-comp-se' },
        { id: 'S', chartId: 'chart-ena-comp-s', chartRef: 'enaCompS', tableId: 'table-ena-comp-s' },
        { id: 'NE', chartId: 'chart-ena-comp-ne', chartRef: 'enaCompNE', tableId: 'table-ena-comp-ne' },
        { id: 'N', chartId: 'chart-ena-comp-n', chartRef: 'enaCompN', tableId: 'table-ena-comp-n' }
    ];
    
    // Cores neon para o layout escuro
    const coresRVs = {
        'RV0': 'rgba(56, 189, 248, 0.45)',  // Ciano translúcido
        'RV1': 'rgba(249, 115, 22, 0.45)',  // Laranja translúcido
        'RV2': 'rgba(168, 85, 247, 0.45)',  // Roxo translúcido
        'RV3': 'rgba(236, 72, 153, 0.45)',  // Rosa translúcido
        'RV4': 'rgba(234, 179, 8, 0.45)'    // Amarelo translúcido
    };
    
    const coresBordasRVs = {
        'RV0': '#38bdf8',
        'RV1': '#f97316',
        'RV2': '#a855f7',
        'RV3': '#ec4899',
        'RV4': '#eab308'
    };
    
    // Cor do Realizado: Verde para Armazenável, Ciano para Bruta
    const corRealizado = variavelRealizado === 'armazenavel' ? '#10b981' : '#06b6d4';
    const labelRealizado = variavelRealizado === 'armazenavel' ? 'Realizado Armazenável' : 'Realizado Bruta';
    
    subsistemas.forEach(subInfo => {
        const subData = dados[subInfo.id];
        if (!subData) return;
        
        // ----------------- RENDERIZAR TABELA COMPARATIVA -----------------
        const tableElement = document.getElementById(subInfo.tableId);
        if (tableElement) {
            let headHtml = `
                <thead>
                    <tr>
                        <th style="text-align: left; font-size: 11px;">Revisão / Real</th>
            `;
            semanasInfo.forEach(sem => {
                headHtml += `<th style="text-align: right; font-size: 11px;">${sem.label.replace('Semana', 'Sem.')} <span style="font-size: 9px; color: var(--text-muted); font-weight: normal; display: block;">(${sem.dias_no_mes} dias)</span></th>`;
            });
            headHtml += `
                        <th style="text-align: right; background: rgba(255, 255, 255, 0.03); font-size: 11px;">Média Mensal</th>
                    </tr>
                </thead>
            `;
            
            let bodyHtml = '<tbody>';
            
            // Previsões das RVs
            const rvs = Object.keys(subData.previsoes).sort();
            rvs.forEach(rv => {
                const prev = subData.previsoes[rv];
                bodyHtml += `
                    <tr>
                        <td style="text-align: left; font-weight: 500; vertical-align: middle;">Previsto ${rv}</td>
                `;
                prev.valores.forEach(val => {
                    let displayCell = '-';
                    if (val !== null) {
                        displayCell = formatNumber(val, 0);
                        if (subData.mlt) {
                            const pct = (val / subData.mlt) * 100;
                            displayCell += `<span style="font-size: 9.5px; color: var(--text-muted); display: block; font-weight: normal; margin-top: 1px;">${formatNumber(pct, 0)}%</span>`;
                        }
                    }
                    bodyHtml += `<td style="text-align: right; vertical-align: middle;">${displayCell}</td>`;
                });
                
                // Média mensal
                let mediaDisplay = '-';
                if (prev.media_mensal !== null) {
                    mediaDisplay = formatNumber(prev.media_mensal, 0);
                    if (subData.mlt) {
                        const pct = (prev.media_mensal / subData.mlt) * 100;
                        mediaDisplay += `<span style="font-size: 9.5px; color: var(--text-muted); display: block; font-weight: normal; margin-top: 1px;">${formatNumber(pct, 0)}%</span>`;
                    }
                }
                bodyHtml += `
                        <td style="text-align: right; font-weight: bold; background: rgba(255, 255, 255, 0.02); vertical-align: middle;">${mediaDisplay}</td>
                    </tr>
                `;
            });
            
            // Realizado
            const realizadoObj = variavelRealizado === 'armazenavel' ? subData.realizado_armazenavel : subData.realizado_bruta;
            bodyHtml += `
                <tr style="border-top: 1.5px solid rgba(255, 255, 255, 0.1); background: rgba(${variavelRealizado === 'armazenavel' ? '16, 185, 129' : '6, 182, 212'}, 0.03);">
                    <td style="text-align: left; vertical-align: middle;"><strong style="color: ${corRealizado};">${labelRealizado}</strong></td>
            `;
            realizadoObj.valores.forEach(val => {
                let displayCell = '-';
                if (val !== null) {
                    displayCell = formatNumber(val, 0);
                    if (subData.mlt) {
                        const pct = (val / subData.mlt) * 100;
                        displayCell += `<span style="font-size: 9.5px; color: var(--text-muted); display: block; font-weight: normal; margin-top: 1px;">${formatNumber(pct, 0)}%</span>`;
                    }
                }
                bodyHtml += `<td style="text-align: right; font-weight: 600; color: ${val !== null ? 'var(--text-primary)' : 'var(--text-muted)'}; vertical-align: middle;">${displayCell}</td>`;
            });
            
            // Média Realizado
            let mediaDisplayReal = '-';
            if (realizadoObj.media_mensal !== null) {
                mediaDisplayReal = formatNumber(realizadoObj.media_mensal, 0);
                if (subData.mlt) {
                    const pct = (realizadoObj.media_mensal / subData.mlt) * 100;
                    mediaDisplayReal += `<span style="font-size: 9.5px; color: var(--text-muted); display: block; font-weight: normal; margin-top: 1px;">${formatNumber(pct, 0)}%</span>`;
                }
            }
            bodyHtml += `
                    <td style="text-align: right; font-weight: bold; color: ${corRealizado}; background: rgba(255, 255, 255, 0.04); vertical-align: middle;">${mediaDisplayReal}</td>
                </tr>
            `;
            
            bodyHtml += '</tbody>';
            tableElement.innerHTML = headHtml + bodyHtml;
        }
        
        // ----------------- RENDERIZAR GRÁFICO -----------------
        const canvas = document.getElementById(subInfo.chartId);
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        
        // Destrói gráfico anterior
        if (charts[subInfo.chartRef]) {
            charts[subInfo.chartRef].destroy();
        }
        
        const datasets = [];
        
        // 1. Adiciona as barras para cada RV disponível no JSON
        const rvs = Object.keys(subData.previsoes).sort();
        rvs.forEach(rv => {
            const coresRV = coresRVs[rv] || 'rgba(255, 255, 255, 0.2)';
            const bordaRV = coresBordasRVs[rv] || '#ffffff';
            
            datasets.push({
                type: 'bar',
                label: `Previsto ${rv}`,
                data: subData.previsoes[rv].valores,
                backgroundColor: coresRV,
                borderColor: bordaRV,
                borderWidth: 1.5,
                borderRadius: 4,
                barPercentage: 0.85,
                categoryPercentage: 0.8
            });
        });
        
        // 2. Adiciona a linha do Realizado
        const realizadoData = variavelRealizado === 'armazenavel' ? subData.realizado_armazenavel.valores : subData.realizado_bruta.valores;
        datasets.push({
            type: 'line',
            label: labelRealizado,
            data: realizadoData,
            borderColor: corRealizado,
            backgroundColor: 'transparent',
            borderWidth: 3.5,
            pointBackgroundColor: corRealizado,
            pointBorderColor: '#09090b',
            pointBorderWidth: 2,
            pointRadius: 5,
            pointHoverRadius: 7,
            tension: 0.15,
            fill: false,
            order: -1 // Garante que a linha fique por cima das barras
        });
        
        // Desenha o gráfico
        charts[subInfo.chartRef] = new Chart(ctx, {
            data: {
                labels: labels,
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(255, 255, 255, 0.03)' },
                        ticks: {
                            color: '#a1a1aa',
                            font: { family: 'Inter', size: 9 }
                        }
                    },
                    y: {
                        type: 'linear',
                        display: true,
                        title: {
                            display: true,
                            text: 'MWmedio',
                            color: '#a1a1aa',
                            font: { family: 'Inter', size: 10 }
                        },
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#a1a1aa', font: { family: 'Inter', size: 10 } }
                    }
                },
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color: '#f4f4f5',
                            font: { family: 'Inter', size: 9 },
                            boxWidth: 10,
                            padding: 10
                        }
                    },
                    tooltip: {
                        backgroundColor: '#18181b',
                        titleColor: '#f4f4f5',
                        bodyColor: '#a1a1aa',
                        borderColor: '#27272a',
                        borderWidth: 1,
                        titleFont: { family: 'Inter', weight: 'bold' },
                        bodyFont: { family: 'Inter' },
                        callbacks: {
                            label: function(context) {
                                let label = context.dataset.label || '';
                                if (label) {
                                    label += ': ';
                                }
                                if (context.raw !== null) {
                                    label += formatNumber(context.raw, 0) + ' MWm';
                                } else {
                                    label += 'Não realizado ainda';
                                }
                                
                                // Se for o dataset de realizado, exibe a variação frente à RV0
                                if (context.dataset.type === 'line' && context.raw !== null) {
                                    const rv0Dataset = context.chart.data.datasets.find(d => d.label === 'Previsto RV0');
                                    if (rv0Dataset && rv0Dataset.data[context.dataIndex] !== null) {
                                        const prevVal = rv0Dataset.data[context.dataIndex];
                                        const diff = context.raw - prevVal;
                                        const pct = (diff / prevVal) * 100;
                                        const sinal = diff >= 0 ? '+' : '';
                                        label += ` (${sinal}${formatNumber(pct, 0)}% vs RV0)`;
                                    }
                                }
                                return label;
                            }
                        }
                    }
                }
            }
        });
    });
}


// ----------------- COMPARATIVO DE CARGA (PREVISTO VS REALIZADO) -----------------
async function loadCargaComparativoMeses() {
    try {
        const select = document.getElementById('carga-comp-mes-select');
        if (!select) return;
        
        const response = await fetch('/api/data/carga_comparativo/meses');
        if (!response.ok) throw new Error('Falha ao buscar meses de comparação da carga.');
        
        const meses = await response.json();
        
        if (meses && meses.length > 0) {
            let html = '';
            meses.forEach(m => {
                html += `<option value="${m.id}">${m.label}</option>`;
            });
            select.innerHTML = html;
            
            // Dispara carregamento dos dados para o primeiro mês
            loadCargaComparativoData();
        } else {
            select.innerHTML = '<option value="">Nenhum mês disponível</option>';
        }
    } catch (error) {
        console.error("Erro ao buscar meses de comparação da Carga:", error);
        showToast('Erro', 'Não foi possível carregar os meses de comparação da Carga.', 'error');
    }
}

async function loadCargaComparativoData() {
    try {
        const select = document.getElementById('carga-comp-mes-select');
        if (!select || !select.value) return;
        
        const mes = select.value;
        
        // Exibe spinner temporário nos canvas
        ['sin', 'se', 's', 'ne', 'n'].forEach(sub => {
            const canvas = document.getElementById(`chart-carga-comp-${sub}`);
            if (canvas) {
                const ctx = canvas.getContext('2d');
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                ctx.font = '14px Inter, sans-serif';
                ctx.fillStyle = '#a1a1aa';
                ctx.textAlign = 'center';
                ctx.fillText('Carregando comparativo...', canvas.width / 2, canvas.height / 2);
            }
        });
        
        const response = await fetch(`/api/data/carga_comparativo?mes=${mes}`);
        if (!response.ok) throw new Error('Erro ao buscar dados do comparativo de Carga.');
        
        rawCargaComparativoData = await response.json();
        
        renderCargaComparativoCharts();
    } catch (error) {
        console.error("Erro ao carregar dados comparativos de Carga:", error);
        showToast('Erro de Carregamento', 'Falha ao buscar dados comparativos de Carga.', 'error');
    }
}

function renderCargaComparativoCharts() {
    if (!rawCargaComparativoData || !rawCargaComparativoData.dados) return;
    
    const semanasInfo = rawCargaComparativoData.semanas_info;
    const dados = rawCargaComparativoData.dados;
    
    // Labels do Eixo X: "Semana 1\n(30/05 a 05/06)" etc.
    const labels = semanasInfo.map(sem => [sem.label, `(${sem.periodo})`]);
    
    const subsistemas = [
        { id: 'SIN', chartId: 'chart-carga-comp-sin', chartRef: 'cargaCompSIN', tableId: 'table-carga-comp-sin' },
        { id: 'SE', chartId: 'chart-carga-comp-se', chartRef: 'cargaCompSE', tableId: 'table-carga-comp-se' },
        { id: 'S', chartId: 'chart-carga-comp-s', chartRef: 'cargaCompS', tableId: 'table-carga-comp-s' },
        { id: 'NE', chartId: 'chart-carga-comp-ne', chartRef: 'cargaCompNE', tableId: 'table-carga-comp-ne' },
        { id: 'N', chartId: 'chart-carga-comp-n', chartRef: 'cargaCompN', tableId: 'table-carga-comp-n' }
    ];
    
    // Cores neon para o layout escuro
    const coresRVs = {
        'RV0': 'rgba(56, 189, 248, 0.45)',  // Ciano translúcido
        'RV1': 'rgba(249, 115, 22, 0.45)',  // Laranja translúcido
        'RV2': 'rgba(168, 85, 247, 0.45)',  // Roxo translúcido
        'RV3': 'rgba(236, 72, 153, 0.45)',  // Rosa translúcido
        'RV4': 'rgba(234, 179, 8, 0.45)'    // Amarelo translúcido
    };
    
    const coresBordasRVs = {
        'RV0': '#38bdf8',
        'RV1': '#f97316',
        'RV2': '#a855f7',
        'RV3': '#ec4899',
        'RV4': '#eab308'
    };
    
    // Cor do Realizado: Amarela
    const corRealizado = '#eab308';
    const labelRealizado = 'Realizado Carga';
    
    subsistemas.forEach(subInfo => {
        const subData = dados[subInfo.id];
        if (!subData) return;
        
        // ----------------- RENDERIZAR TABELA COMPARATIVA -----------------
        const tableElement = document.getElementById(subInfo.tableId);
        if (tableElement) {
            let headHtml = `
                <thead>
                    <tr>
                        <th style="text-align: left; font-size: 11px;">Revisão / Real</th>
            `;
            semanasInfo.forEach(sem => {
                headHtml += `<th style="text-align: right; font-size: 11px;">${sem.label.replace('Semana', 'Sem.')} <span style="font-size: 9px; color: var(--text-muted); font-weight: normal; display: block;">(${sem.dias_no_mes} dias)</span></th>`;
            });
            headHtml += `
                        <th style="text-align: right; background: rgba(255, 255, 255, 0.03); font-size: 11px;">Média Mensal</th>
                    </tr>
                </thead>
            `;
            
            let bodyHtml = '<tbody>';
            
            // Previsões das RVs
            const rvs = Object.keys(subData.previsoes).sort();
            rvs.forEach(rv => {
                const prev = subData.previsoes[rv];
                bodyHtml += `
                    <tr>
                        <td style="text-align: left; font-weight: 500; vertical-align: middle;">Previsto ${rv}</td>
                `;
                prev.valores.forEach(val => {
                    let displayCell = '-';
                    if (val !== null) {
                        displayCell = formatNumber(val, 0);
                    }
                    bodyHtml += `<td style="text-align: right; vertical-align: middle;">${displayCell}</td>`;
                });
                
                // Média mensal
                let mediaDisplay = '-';
                if (prev.media_mensal !== null) {
                    mediaDisplay = formatNumber(prev.media_mensal, 0);
                }
                bodyHtml += `
                        <td style="text-align: right; font-weight: bold; background: rgba(255, 255, 255, 0.02); vertical-align: middle;">${mediaDisplay}</td>
                    </tr>
                `;
            });
            
            // Realizado
            const realizadoObj = subData.realizado;
            bodyHtml += `
                <tr style="border-top: 1.5px solid rgba(255, 255, 255, 0.1); background: rgba(234, 179, 8, 0.03);">
                    <td style="text-align: left; vertical-align: middle;"><strong style="color: ${corRealizado};">${labelRealizado}</strong></td>
            `;
            realizadoObj.valores.forEach(val => {
                let displayCell = '-';
                if (val !== null) {
                    displayCell = formatNumber(val, 0);
                }
                bodyHtml += `<td style="text-align: right; font-weight: 600; color: ${val !== null ? 'var(--text-primary)' : 'var(--text-muted)'}; vertical-align: middle;">${displayCell}</td>`;
            });
            
            // Média Realizado
            let mediaDisplayReal = '-';
            if (realizadoObj.media_mensal !== null) {
                mediaDisplayReal = formatNumber(realizadoObj.media_mensal, 0);
            }
            bodyHtml += `
                    <td style="text-align: right; font-weight: bold; color: ${corRealizado}; background: rgba(255, 255, 255, 0.04); vertical-align: middle;">${mediaDisplayReal}</td>
                </tr>
            `;
            
            bodyHtml += '</tbody>';
            tableElement.innerHTML = headHtml + bodyHtml;
        }
        
        // ----------------- RENDERIZAR GRÁFICO -----------------
        const canvas = document.getElementById(subInfo.chartId);
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        
        // Destrói gráfico anterior
        if (charts[subInfo.chartRef]) {
            charts[subInfo.chartRef].destroy();
        }
        
        const datasets = [];
        
        // 1. Adiciona as barras para cada RV disponível no JSON
        const rvs = Object.keys(subData.previsoes).sort();
        rvs.forEach(rv => {
            const coresRV = coresRVs[rv] || 'rgba(255, 255, 255, 0.2)';
            const bordaRV = coresBordasRVs[rv] || '#ffffff';
            
            datasets.push({
                type: 'bar',
                label: `Previsto ${rv}`,
                data: subData.previsoes[rv].valores,
                backgroundColor: coresRV,
                borderColor: bordaRV,
                borderWidth: 1.5,
                borderRadius: 4,
                barPercentage: 0.85,
                categoryPercentage: 0.8
            });
        });
        
        // 2. Adiciona a linha do Realizado
        const realizadoData = subData.realizado.valores;
        datasets.push({
            type: 'line',
            label: labelRealizado,
            data: realizadoData,
            borderColor: corRealizado,
            backgroundColor: 'transparent',
            borderWidth: 3.5,
            pointBackgroundColor: corRealizado,
            pointBorderColor: '#09090b',
            pointBorderWidth: 2,
            pointRadius: 5,
            pointHoverRadius: 7,
            tension: 0.15,
            fill: false,
            order: -1
        });
        
        // Desenha o gráfico
        charts[subInfo.chartRef] = new Chart(ctx, {
            data: {
                labels: labels,
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(255, 255, 255, 0.03)' },
                        ticks: {
                            color: '#a1a1aa',
                            font: { family: 'Inter', size: 9 }
                        }
                    },
                    y: {
                        type: 'linear',
                        display: true,
                        title: {
                            display: true,
                            text: 'MWmedio',
                            color: '#a1a1aa',
                            font: { family: 'Inter', size: 10 }
                        },
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#a1a1aa', font: { family: 'Inter', size: 10 } }
                    }
                },
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color: '#f4f4f5',
                            font: { family: 'Inter', size: 9 },
                            boxWidth: 10,
                            padding: 10
                        }
                    },
                    tooltip: {
                        backgroundColor: '#18181b',
                        titleColor: '#f4f4f5',
                        bodyColor: '#a1a1aa',
                        borderColor: '#27272a',
                        borderWidth: 1,
                        titleFont: { family: 'Inter', weight: 'bold' },
                        bodyFont: { family: 'Inter' },
                        callbacks: {
                            label: function(context) {
                                let label = context.dataset.label || '';
                                if (label) {
                                    label += ': ';
                                }
                                if (context.raw !== null) {
                                    label += formatNumber(context.raw, 0) + ' MWm';
                                } else {
                                    label += 'Não realizado ainda';
                                }
                                
                                // Se for o dataset de realizado, exibe a variação frente à RV0
                                if (context.dataset.type === 'line' && context.raw !== null) {
                                    const rv0Dataset = context.chart.data.datasets.find(d => d.label === 'Previsto RV0');
                                    if (rv0Dataset && rv0Dataset.data[context.dataIndex] !== null) {
                                        const prevVal = rv0Dataset.data[context.dataIndex];
                                        const diff = context.raw - prevVal;
                                        const pct = (diff / prevVal) * 100;
                                        const sinal = diff >= 0 ? '+' : '';
                                        label += ` (${sinal}${formatNumber(pct, 0)}% vs RV0)`;
                                    }
                                }
                                return label;
                            }
                        }
                    }
                }
            }
        });
    });
}

// ----------------- COMPARATIVO DE RESERVATÓRIO (EAR) (PREVISTO VS REALIZADO) -----------------
let rawEarComparativoData = null;

async function loadEarComparativoMeses() {
    try {
        const select = document.getElementById('ear-comp-mes-select');
        if (!select) return;
        
        const response = await fetch('/api/data/ear_comparativo/meses');
        if (!response.ok) throw new Error('Falha ao buscar meses de comparação do EAR.');
        
        const meses = await response.json();
        
        if (meses && meses.length > 0) {
            let html = '';
            meses.forEach(m => {
                html += `<option value="${m.id}">${m.label}</option>`;
            });
            select.innerHTML = html;
            
            // Dispara carregamento dos dados para o primeiro mês
            loadEarComparativoData();
        } else {
            select.innerHTML = '<option value="">Nenhum mês disponível</option>';
        }
    } catch (error) {
        console.error("Erro ao buscar meses de comparação do EAR:", error);
        showToast('Erro', 'Não foi possível carregar os meses de comparação do EAR.', 'error');
    }
}

async function loadEarComparativoData() {
    try {
        const select = document.getElementById('ear-comp-mes-select');
        if (!select || !select.value) return;
        
        const mes = select.value;
        
        // Exibe spinner temporário nos canvas
        ['se', 's', 'ne', 'n'].forEach(sub => {
            const canvas = document.getElementById(`chart-ear-comp-${sub}`);
            if (canvas) {
                const ctx = canvas.getContext('2d');
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                ctx.font = '14px Inter, sans-serif';
                ctx.fillStyle = '#a1a1aa';
                ctx.textAlign = 'center';
                ctx.fillText('Carregando comparativo...', canvas.width / 2, canvas.height / 2);
            }
        });
        
        const response = await fetch(`/api/data/ear_comparativo?mes=${mes}`);
        if (!response.ok) throw new Error('Erro ao buscar dados do comparativo de EAR.');
        
        rawEarComparativoData = await response.json();
        
        renderEarComparativoCharts();
    } catch (error) {
        console.error("Erro ao carregar dados comparativos de EAR:", error);
        showToast('Erro de Carregamento', 'Falha ao buscar dados comparativos de EAR.', 'error');
    }
}

function renderEarComparativoCharts() {
    if (!rawEarComparativoData || !rawEarComparativoData.dados) return;
    
    const dias = rawEarComparativoData.dias;
    const dados = rawEarComparativoData.dados;
    
    // ----------------- RENDERIZAR TABELA DE EVOLUÇÃO DIÁRIA RECENTE -----------------
    const tableEvolucaoEl = document.getElementById('table-ear-evolucao-recente');
    if (tableEvolucaoEl) {
        // Encontra o último dia com dados válidos na série
        let ultimoIdx = -1;
        const seReal = dados.SE ? dados.SE.realizado_percentual : [];
        for (let i = seReal.length - 1; i >= 0; i--) {
            if (seReal[i] !== null && seReal[i] !== undefined) {
                ultimoIdx = i;
                break;
            }
        }
        
        if (ultimoIdx === -1) {
            tableEvolucaoEl.innerHTML = '<tbody><tr><td style="text-align: center; padding: 20px; color: var(--text-muted);">Sem dados realizados disponíveis para o mês selecionado.</td></tr></tbody>';
        } else {
            // Seleciona até os últimos 7 dias com dados realizados
            const numColunas = 7;
            const primeiroColIdx = Math.max(0, ultimoIdx - (numColunas - 1));
            const indicesColunas = [];
            for (let i = primeiroColIdx; i <= ultimoIdx; i++) {
                indicesColunas.push(i);
            }
            
            // Cabeçalho
            let headHtml = `
                <thead>
                    <tr>
                        <th style="text-align: left; width: 220px; font-size: 11px;">Subsistema</th>
            `;
            indicesColunas.forEach(idx => {
                const dataStr = dias[idx];
                const partes = dataStr.split('-');
                const diaMes = `${partes[2]}/${partes[1]}`;
                headHtml += `<th style="text-align: center; font-size: 11px;">${diaMes}</th>`;
            });
            headHtml += `
                        <th style="text-align: center; width: 160px; background: rgba(255,255,255,0.02); font-size: 11px;">Variação no Mês (Acumulado)</th>
                    </tr>
                </thead>
            `;
            
            // Linhas dos subsistemas
            const subsMap = [
                { id: 'SE', nome: 'Sudeste / Centro-Oeste' },
                { id: 'S', nome: 'Sul' },
                { id: 'NE', nome: 'Nordeste' },
                { id: 'N', nome: 'Norte' }
            ];
            
            let bodyHtml = '<tbody>';
            subsMap.forEach(sub => {
                const subData = dados[sub.id];
                if (!subData) return;
                const realizado = subData.realizado_percentual;
                
                bodyHtml += `<tr><td style="text-align: left; font-weight: 500; font-size: 12px;"><strong>${sub.nome}</strong></td>`;
                
                indicesColunas.forEach(idx => {
                    const val = realizado[idx];
                    let cellHtml = '-';
                    
                    if (val !== null && val !== undefined) {
                        // Calcula variação do dia anterior
                        let valAnterior = null;
                        if (idx > 0) {
                            valAnterior = realizado[idx - 1];
                        }
                        
                        let diffHtml = '';
                        if (valAnterior !== null && valAnterior !== undefined) {
                            const diff = val - valAnterior;
                            if (diff > 0.005) {
                                diffHtml = `<span style="color: #10b981; font-size: 9.5px; display: block; margin-top: 2px; font-weight: 500;"><i class="fa-solid fa-caret-up"></i> +${formatNumber(diff, 1)}%</span>`;
                            } else if (diff < -0.005) {
                                diffHtml = `<span style="color: #f43f5e; font-size: 9.5px; display: block; margin-top: 2px; font-weight: 500;"><i class="fa-solid fa-caret-down"></i> ${formatNumber(diff, 1)}%</span>`;
                            } else {
                                diffHtml = `<span style="color: #71717a; font-size: 9.5px; display: block; margin-top: 2px; font-weight: 500;">= 0.0%</span>`;
                            }
                        } else {
                            diffHtml = `<span style="color: #71717a; font-size: 9.5px; display: block; margin-top: 2px; font-weight: 500;">-</span>`;
                        }
                        
                        cellHtml = `
                            <div style="text-align: center;">
                                <span style="font-weight: 600; font-size: 12px; color: var(--text-primary);">${formatNumber(val, 1)}%</span>
                                ${diffHtml}
                            </div>
                        `;
                    }
                    
                    bodyHtml += `<td style="vertical-align: middle; text-align: center;">${cellHtml}</td>`;
                });
                
                // Calcula variação acumulada do mês (Último dia contra o Dia 01)
                let primeiroVal = realizado[0];
                if (primeiroVal === null || primeiroVal === undefined) {
                    for (let i = 0; i < realizado.length; i++) {
                        if (realizado[i] !== null && realizado[i] !== undefined) {
                            primeiroVal = realizado[i];
                            break;
                        }
                    }
                }
                
                const ultimoVal = realizado[ultimoIdx];
                let acumuladoHtml = '-';
                
                if (primeiroVal !== null && primeiroVal !== undefined && ultimoVal !== null && ultimoVal !== undefined) {
                    const diffMes = ultimoVal - primeiroVal;
                    let style = '';
                    let icon = '';
                    let sinal = '';
                    
                    if (diffMes > 0.005) {
                        style = 'color: #10b981; font-weight: bold; background: rgba(16, 185, 129, 0.08); border-radius: 4px; padding: 4px 10px; border: 1px solid rgba(16, 185, 129, 0.2); font-size: 11px;';
                        icon = '<i class="fa-solid fa-arrow-trend-up" style="margin-right: 4px;"></i>';
                        sinal = '+';
                    } else if (diffMes < -0.005) {
                        style = 'color: #f43f5e; font-weight: bold; background: rgba(244, 63, 94, 0.08); border-radius: 4px; padding: 4px 10px; border: 1px solid rgba(244, 63, 94, 0.2); font-size: 11px;';
                        icon = '<i class="fa-solid fa-arrow-trend-down" style="margin-right: 4px;"></i>';
                    } else {
                        style = 'color: #a1a1aa; font-weight: bold; background: rgba(161, 161, 170, 0.08); border-radius: 4px; padding: 4px 10px; border: 1px solid rgba(161, 161, 170, 0.2); font-size: 11px;';
                        icon = '= ';
                    }
                    
                    acumuladoHtml = `
                        <div style="text-align: center; display: inline-block; ${style}">
                            ${icon}${sinal}${formatNumber(diffMes, 1)}%
                        </div>
                    `;
                }
                
                bodyHtml += `<td style="text-align: center; vertical-align: middle; background: rgba(255,255,255,0.01);">${acumuladoHtml}</td></tr>`;
            });
            bodyHtml += '</tbody>';
            tableEvolucaoEl.innerHTML = headHtml + bodyHtml;
        }
    }
    
    // Labels do Eixo X: formatados para DD/MM
    const labels = dias.map(d => {
        const partes = d.split('-');
        if (partes.length === 3) {
            return `${partes[2]}/${partes[1]}`;
        }
        return d;
    });
    
    const subsistemas = [
        { id: 'SE', chartId: 'chart-ear-comp-se', chartRef: 'earCompSE', tableId: 'table-ear-comp-se' },
        { id: 'S', chartId: 'chart-ear-comp-s', chartRef: 'earCompS', tableId: 'table-ear-comp-s' },
        { id: 'NE', chartId: 'chart-ear-comp-ne', chartRef: 'earCompNE', tableId: 'table-ear-comp-ne' },
        { id: 'N', chartId: 'chart-ear-comp-n', chartRef: 'earCompN', tableId: 'table-ear-comp-n' }
    ];
    
    const coresRVs = {
        'RV0': '#38bdf8',  // Ciano
        'RV1': '#f97316',  // Laranja
        'RV2': '#a855f7',  // Roxo
        'RV3': '#ec4899',  // Rosa
        'RV4': '#eab308'   // Amarelo
    };
    
    const corRealizado = '#2dd4bf'; // Teal/Turquesa
    
    subsistemas.forEach(subInfo => {
        const subData = dados[subInfo.id];
        if (!subData) return;
        
        const capMax = subData.capacidade_maxima; // Em MWmês
        
        // ----------------- RENDERIZAR TABELA COMPARATIVA -----------------
        const tableElement = document.getElementById(subInfo.tableId);
        if (tableElement) {
            let headHtml = `
                <thead>
                    <tr>
                        <th style="text-align: left; font-size: 11px;">Revisão / Real</th>
                        <th style="text-align: right; font-size: 11px;">Nível (%)</th>
                        <th style="text-align: right; font-size: 11px;">Energia (MWmês)</th>
                    </tr>
                </thead>
            `;
            
            let bodyHtml = '<tbody>';
            
            // Previsões de Fechamento por RV
            const rvs = Object.keys(subData.previsoes).sort();
            rvs.forEach(rv => {
                const prevVal = subData.previsoes[rv]; // Em %
                let displayPct = '-';
                let displayMw = '-';
                
                if (prevVal !== null) {
                    displayPct = formatNumber(prevVal, 1) + '%';
                    if (capMax !== null) {
                        const mwmes = (prevVal / 100) * capMax;
                        displayMw = formatNumber(mwmes, 0) + ' MWmês';
                    }
                }
                
                bodyHtml += `
                    <tr>
                        <td style="text-align: left; font-weight: 500;">Previsto ${rv}</td>
                        <td style="text-align: right;">${displayPct}</td>
                        <td style="text-align: right; color: var(--text-secondary);">${displayMw}</td>
                    </tr>
                `;
            });
            
            // Realizado Atual
            const ultimo = subData.ultimo_realizado;
            let displayRealPct = '-';
            let displayRealMw = '-';
            let labelReal = 'Realizado';
            
            if (ultimo && ultimo.percentual !== null) {
                displayRealPct = formatNumber(ultimo.percentual, 1) + '%';
                displayRealMw = formatNumber(ultimo.mwmes, 0) + ' MWmês';
                labelReal = `Realizado Atual (${ultimo.data})`;
            }
            
            bodyHtml += `
                <tr style="border-top: 1.5px solid rgba(255, 255, 255, 0.1); background: rgba(45, 212, 191, 0.03);">
                    <td style="text-align: left;"><strong style="color: ${corRealizado};">${labelReal}</strong></td>
                    <td style="text-align: right; font-weight: 600; color: ${corRealizado};">${displayRealPct}</td>
                    <td style="text-align: right; font-weight: 600; color: ${corRealizado};">${displayRealMw}</td>
                </tr>
            `;
            
            bodyHtml += '</tbody>';
            tableElement.innerHTML = headHtml + bodyHtml;
        }
        
        // ----------------- RENDERIZAR GRÁFICO -----------------
        const canvas = document.getElementById(subInfo.chartId);
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        
        // Destrói gráfico anterior se houver
        if (charts[subInfo.chartRef]) {
            charts[subInfo.chartRef].destroy();
        }
        
        const datasets = [];
        
        // 1. Adiciona as linhas horizontais tracejadas para cada RV (Previsões de Fechamento)
        const rvs = Object.keys(subData.previsoes).sort();
        rvs.forEach(rv => {
            const valPrev = subData.previsoes[rv];
            if (valPrev !== null) {
                const corRV = coresRVs[rv] || '#ffffff';
                
                // Repete o valor para todos os pontos do gráfico para desenhar a linha horizontal
                const dataVals = labels.map(() => valPrev);
                
                datasets.push({
                    type: 'line',
                    label: `Previsto Fechamento ${rv}`,
                    data: dataVals,
                    borderColor: corRV,
                    borderDash: [5, 5],
                    borderWidth: 1.5,
                    pointRadius: 0,
                    pointHoverRadius: 0,
                    fill: false
                });
            }
        });
        
        // 2. Adiciona a linha do Realizado Diário
        const realizadoData = subData.realizado_percentual;
        datasets.push({
            type: 'line',
            label: 'Realizado Diário',
            data: realizadoData,
            borderColor: corRealizado,
            backgroundColor: 'rgba(45, 212, 191, 0.05)',
            borderWidth: 3,
            pointBackgroundColor: corRealizado,
            pointBorderColor: '#09090b',
            pointBorderWidth: 1.5,
            pointRadius: realizadoData.map(v => v !== null ? 2 : 0),
            pointHoverRadius: 5,
            tension: 0.1,
            fill: true,
            order: -1 // Por cima das linhas tracejadas
        });
        
        // Desenha o gráfico
        charts[subInfo.chartRef] = new Chart(ctx, {
            data: {
                labels: labels,
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(255, 255, 255, 0.03)' },
                        ticks: {
                            color: '#a1a1aa',
                            font: { family: 'Inter', size: 9 },
                            maxTicksLimit: 12
                        }
                    },
                    y: {
                        type: 'linear',
                        display: true,
                        title: {
                            display: true,
                            text: 'Nível (%)',
                            color: '#a1a1aa',
                            font: { family: 'Inter', size: 10 }
                        },
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: {
                            color: '#a1a1aa',
                            font: { family: 'Inter', size: 10 },
                            callback: function(value) { return value + '%'; }
                        }
                    }
                },
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color: '#f4f4f5',
                            font: { family: 'Inter', size: 9 },
                            boxWidth: 10,
                            padding: 8
                        }
                    },
                    tooltip: {
                        backgroundColor: '#18181b',
                        titleColor: '#f4f4f5',
                        bodyColor: '#a1a1aa',
                        borderColor: '#27272a',
                        borderWidth: 1,
                        titleFont: { family: 'Inter', weight: 'bold' },
                        bodyFont: { family: 'Inter' },
                        callbacks: {
                            label: function(context) {
                                let label = context.dataset.label || '';
                                if (label) {
                                    label += ': ';
                                }
                                if (context.raw !== null) {
                                    label += formatNumber(context.raw, 1) + '%';
                                    
                                    // Se for o realizado diário, também mostra o valor correspondente em MWmês
                                    if (context.dataset.label === 'Realizado Diário' && capMax !== null) {
                                        const mwmes = (context.raw / 100) * capMax;
                                        label += ` (${formatNumber(mwmes, 0)} MWmês)`;
                                    }
                                } else {
                                    label += 'Sem dados';
                                }
                                return label;
                            }
                        }
                    }
                }
            }
        });
    });
}
