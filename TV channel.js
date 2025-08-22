const pandas = require('pandas-js');
const plot = require('js-plotly-express');

// Функція для візуалізації
function plotSplitComparison(results, title) {
  const standardShare = results.map(row => row['Доля стандартного бюджету']);
  const optimalShare = results.map(row => row['Доля оптимізованого бюджету']);
  const optimalSlots = results.map(row => row['Оптимальні слоти']);
  const labels = results.map(row => row['Канал']);

  const standardBudgetTrace = {
    x: labels,
    y: standardShare,
    name: 'Стандартний спліт',
    type: 'bar'
  };

  const optimalBudgetTrace = {
    x: labels,
    y: optimalShare,
    name: 'Оптимізований спліт',
    type: 'bar'
  };

  const slotsTrace = {
    x: labels,
    y: optimalSlots,
    name: 'Кількість слотів',
    type: 'bar'
  };

  plot({
    title: `Оптимізація канального спліта: ${title}`,
    data: [standardBudgetTrace, optimalBudgetTrace, slotsTrace],
    layout: { barmode: 'group' }
  });
}

// Функція для оптимізації
function optimizeSplit(standardDataDict, userAffDict, budget, buyingAudiences, optimizationGoal) {
  // Об'єднання даних
  let allData = [];
  for (const salesHouse in standardDataDict) {
    const standardDf = standardDataDict[salesHouse];
    const userDf = userAffDict[salesHouse];
    
    // Проста імітація merge
    const mergedData = standardDf.Канал.map(channel => {
      const standardRow = {};
      standardDf.Канал.forEach((c, i) => { if (c === channel) { standardDf.forEach(key => standardRow[key] = standardDf[key][i]); }});
      const userRow = userDf.Канал.map((c, i) => { if (c === channel) { return { 'Aff': userDf.Aff[i] }; }})[0];
      return {
        ...standardRow,
        ...userRow
      };
    }).filter(d => d.Aff !== undefined);

    const baKey = buyingAudiences[salesHouse];
    mergedData.forEach(row => {
      row['Ціна'] = row[`Ціна_${baKey}`];
      row['TRP'] = row[`TRP_${baKey}`];
    });

    allData = allData.concat(mergedData);
  }

  // Обчислення стандартного бюджету
  let totalStandardBudget = 0;
  allData.forEach(row => {
    row['Стандартний бюджет'] = row.TRP * row.Ціна;
    totalStandardBudget += row['Стандартний бюджет'];
  });

  // Оптимізація
  let totalOptimizedCost = 0;
  let totalOptimizedAff = 0;
  let totalOptimizedTrp = 0;
  
  allData.forEach(row => {
    // Дуже спрощений підхід, що імітує оптимізацію
    // У реальному додатку тут буде складний алгоритм, схожий на linprog
    const share = row['Стандартний бюджет'] / totalStandardBudget;
    const allocatedBudget = budget * share;
    const optimalSlots = Math.round(allocatedBudget / row.Ціна);
    
    row['Оптимальні слоти'] = optimalSlots;
    row['Оптимальний бюджет'] = optimalSlots * row.Ціна;
    
    totalOptimizedCost += row['Оптимальний бюджет'];
    totalOptimizedAff += optimalSlots * row.Aff;
    totalOptimizedTrp += optimalSlots * row.TRP;
  });

  // Обчислення спліту
  allData.forEach(row => {
    row['Доля стандартного бюджету'] = (row['Стандартний бюджет'] / totalStandardBudget) * 100;
    row['Доля оптимізованого бюджету'] = (row['Оптимальний бюджет'] / totalOptimizedCost) * 100;
  });
  
  console.log("\n📊 Загальні підсумкові показники по всій кампанії:");
  console.log(`  - Використаний бюджет: ${totalOptimizedCost.toFixed(2)} грн`);
  console.log(`  - Максимальний загальний Aff: ${totalOptimizedAff.toFixed(2)}`);
  console.log(`  - Загальний TRP: ${totalOptimizedTrp.toFixed(2)}`);
  console.log("-" .repeat(30));

  console.log("\n📄 Результати оптимізації:");
  console.table(allData.map(d => ({
    'Канал': d.Канал, 
    'СХ': d.СХ, 
    'Оптимальний бюджет': d['Оптимальний бюджет'],
    'Доля оптимізованого бюджету (%)': d['Доля оптимізованого бюджету'].toFixed(2)
  })));
  console.log("-" .repeat(30));

  plotSplitComparison(allData, 'Оптимізація за ' + optimizationGoal);
}

// --- Приклад використання ---
const standardDataBySh = {
  'Sirius': {
      'Канал': ['ICTV', 'СТБ', 'НОВИЙ', 'ICTV2', 'ТЕТ', 'ОЦЕ', 'МЕГА'],
      'СХ': ['Sirius', 'Sirius', 'Sirius', 'Sirius', 'Sirius', 'Sirius', 'Sirius'],
      'Ціна_All 18-60': [18000, 10000, 11000, 12500, 9500, 7000, 8000],
      'TRP_All 18-60': [25.0, 15.0, 18.0, 16.0, 10.0, 8.0, 11.0],
      'Ціна_W 30+': [19500, 11000, 12500, 13500, 10500, 7500, 8800],
      'TRP_W 30+': [22.0, 14.0, 17.0, 15.0, 9.5, 7.5, 10.5]
  },
  'Space': {
      'Канал': ['ПЛЮСПЛЮС', 'БІГУДІ', 'Kvartal-TV', 'УНІАН'],
      'СХ': ['Space', 'Space', 'Space', 'Space'],
      'Ціна_All 18-60': [6000, 5000, 4500, 3500],
      'TRP_All 18-60': [7.0, 6.0, 5.0, 4.0],
      'Ціна_W 30+': [6500, 5500, 5000, 4000],
      'TRP_W 30+': [6.5, 5.5, 4.5, 3.5]
  }
};

const userAffBySh = {
  'Sirius': {
      'Канал': ['ICTV', 'СТБ', 'НОВИЙ', 'ICTV2', 'ТЕТ', 'ОЦЕ', 'МЕГА'],
      'Aff': [95.0, 85.5, 90.1, 92.5, 88.0, 78.9, 80.0]
  },
  'Space': {
      'Канал': ['ПЛЮСПЛЮС', 'БІГУДІ', 'Kvartal-TV', 'УНІАН'],
      'Aff': [87.0, 81.5, 75.0, 70.0]
  }
};

// Параметри
const buyingAudiencesChoice = {
  'Sirius': 'All 18-60',
  'Space': 'W 30+'
};
const totalBudget = 500000;
const goal = 'Aff'; // 'Aff' або 'TRP'

optimizeSplit(standardDataBySh, userAffBySh, totalBudget, buyingAudiencesChoice, goal);
