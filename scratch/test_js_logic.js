const fs = require('fs');
const path = require('path');

const cachePath = path.join(__dirname, '..', 'planilhas_para_atualizar', 'bbce_diario_cache.json');
if (!fs.existsSync(cachePath)) {
    console.log("Cache file does not exist.");
    process.exit(1);
}

const rawBbceData = JSON.parse(fs.readFileSync(cachePath, 'utf8'));
console.log("Total records:", rawBbceData.length);

let maxDateStr = "";
rawBbceData.forEach(d => {
    if (d.DATA_DIA && d.DATA_DIA > maxDateStr) {
        maxDateStr = d.DATA_DIA;
    }
});
console.log("maxDateStr:", maxDateStr);

let limitDateStr = "";
if (maxDateStr) {
    const maxDate = new Date(maxDateStr + 'T12:00:00');
    const threeMonthsAgo = new Date(maxDate);
    threeMonthsAgo.setMonth(threeMonthsAgo.getMonth() - 3);
    limitDateStr = threeMonthsAgo.toISOString().split('T')[0];
}
console.log("limitDateStr:", limitDateStr);

let countMap = {};
rawBbceData.forEach(d => {
    if (d.PRODUTO && (!limitDateStr || d.DATA_DIA >= limitDateStr)) {
        countMap[d.PRODUTO] = (countMap[d.PRODUTO] || 0) + (d.total_contratos || 1);
    }
});

const sortedProductsByCount = Object.keys(countMap).sort((a, b) => countMap[b] - countMap[a]);
console.log("Top products:", sortedProductsByCount.slice(0, 10).map(p => ({ product: p, count: countMap[p] })));

const defaultSelection = sortedProductsByCount.slice(0, 3);
console.log("Default selection:", defaultSelection);
