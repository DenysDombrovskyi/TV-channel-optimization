import pandas as pd
from scipy.optimize import linprog
import matplotlib.pyplot as plt

def save_results_to_excel(results_df, file_name):
    """
    Зберігає результати оптимізації у файл Excel.
    """
    try:
        results_df.to_excel(file_name, index=False)
        print(f"\n✅ Результати оптимізації успішно збережено у файл: '{file_name}'")
    except Exception as e:
        print(f"\n❌ Помилка при збереженні файлу: {e}")

def plot_split_comparison(results_df, title):
    """
    Будує діаграми для порівняння сплітів.
    """
    # Обчислення частки бюджету
    results_df['Доля стандартного бюджету'] = (results_df['Стандартний бюджет'] / results_df['Стандартний бюджет'].sum()) * 100
    results_df['Доля оптимізованого бюджету'] = (results_df['Оптимальний бюджет'] / results_df['Оптимальний бюджет'].sum()) * 100
    
    fig, axes = plt.subplots(1, 2, figsize=(18, 8))
    fig.suptitle(f'Оптимізація канального спліта: {title}', fontsize=16)

    # Графік 1: Розподіл частки бюджету
    axes[0].set_title('Порівняння частки бюджету (%)')
    labels = results_df['Канал']
    standard_share = results_df['Доля стандартного бюджету']
    optimal_share = results_df['Доля оптимізованого бюджету']
    
    x = range(len(labels))
    width = 0.35
    
    rects1 = axes[0].bar(x, standard_share, width, label='Стандартний спліт', color='gray')
    rects2 = axes[0].bar([p + width for p in x], optimal_share, width, label='Оптимізований спліт', color='skyblue')

    axes[0].set_ylabel('Частка бюджету, %')
    axes[0].set_xticks([p + width / 2 for p in x])
    axes[0].set_xticklabels(labels, rotation=45, ha="right")
    axes[0].legend()
    axes[0].grid(axis='y', linestyle='--', alpha=0.7)
    
    # Графік 2: Кількість слотів
    axes[1].set_title('Кількість слотів (Оптимізований спліт)')
    optimal_slots = results_df['Оптимальні слоти']
    
    axes[1].bar(labels, optimal_slots, color='skyblue')
    axes[1].set_ylabel('Кількість слотів')
    axes[1].set_xticklabels(labels, rotation=45, ha="right")
    axes[1].grid(axis='y', linestyle='--', alpha=0.7)

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.show()

def optimize_split(standard_data_dict, user_aff_dict, budget, buying_audiences, optimization_goal, optimization_mode):
    """
    Основна функція для оптимізації канального спліта з урахуванням різних режимів.
    
    Параметри:
    - standard_data_dict (dict): Словник зі стандартними даними.
    - user_aff_dict (dict): Словник з даними Aff від користувача.
    - budget (int): Загальний рекламний бюджет.
    - buying_audiences (dict): Словник {СХ: БА}.
    - optimization_goal (str): 'Aff' або 'TRP'.
    - optimization_mode (str): 'per_sh' або 'total'.
    """
    
    # Об'єднання всіх даних в один DataFrame для зручності
    all_data = pd.DataFrame()
    for sales_house in standard_data_dict:
        try:
            standard_df = pd.DataFrame(standard_data_dict[sales_house])
            user_df = pd.DataFrame(user_aff_dict[sales_house])
            merged_df = pd.merge(standard_df, user_df, on='Канал')
            
            ba_key = buying_audiences.get(sales_house)
            if ba_key:
                merged_df['Ціна'] = merged_df[f'Ціна_{ba_key}']
                merged_df['TRP'] = merged_df[f'TRP_{ba_key}']
            
            all_data = pd.concat([all_data, merged_df], ignore_index=True)
            
        except KeyError:
            print(f"Помилка: Немає даних для БА '{ba_key}' або СХ '{sales_house}'.")
            return None
    
    if all_data.empty:
        print("Помилка: Не вдалося завантажити дані для оптимізації.")
        return None

    all_results = pd.DataFrame()
    
    # Режим "Оптимізація по кожному СХ окремо"
    if optimization_mode == 'per_sh':
        print("\nВибрано режим: Оптимізація по кожному СХ окремо.")
        
        # Розрахунок загального стандартного бюджету для визначення частки кожного СХ
        total_standard_budget = (all_data['TRP'] * all_data['Ціна']).sum()

        for sales_house, group_df in all_data.groupby('СХ'):
            print(f"✅ Проводимо оптимізацію для СХ: {sales_house}")
            
            group_standard_budget = (group_df['TRP'] * group_df['Ціна']).sum()
            group_budget = (group_standard_budget / total_standard_budget) * budget
            
            group_df['Стандартний бюджет'] = group_df['TRP'] * group_df['Ціна']
            group_df['Доля по бюджету (%)'] = (group_df['Стандартний бюджет'] / group_df['Стандартний бюджет'].sum()) * 100
            
            group_df['Відхилення'] = group_df.apply(lambda row: 0.20 if row['Доля по бюджету (%)'] >= 10 else 0.30, axis=1)
            group_df['Нижня межа'] = group_df['Стандартний бюджет'] * (1 - group_df['Відхилення'])
            group_df['Верхня межа'] = group_df['Стандартний бюджет'] * (1 + group_df['Відхилення'])
            
            c = -group_df[optimization_goal].values
            A_ub_group = [group_df['Ціна'].values]
            b_ub_group = [group_budget]
            A_lower = -pd.get_dummies(group_df['Канал']).mul(group_df['Ціна'], axis=0).values
            b_lower = -group_df['Нижня межа'].values
            A_upper = pd.get_dummies(group_df['Канал']).mul(group_df['Ціна'], axis=0).values
            b_upper = group_df['Верхня межа'].values
            A_group = [A_ub_group[0]] + list(A_lower) + list(A_upper)
            b_group = b_ub_group + list(b_lower) + list(b_upper)
            
            result = linprog(c, A_ub=A_group, b_ub=b_group, bounds=(0, None))
            
            if result.success:
                optimal_slots = result.x.round(0).astype(int)
                group_df['Оптимальні слоти'] = optimal_slots
                group_df['Оптимальний бюджет'] = optimal_slots * group_df['Ціна']
                all_results = pd.concat([all_results, group_df])
            else:
                print(f"❌ Помилка оптимізації для {sales_house}:", result.message)

    # Режим "Оптимізація по всьому бюджету"
    elif optimization_mode == 'total':
        print("\nВибрано режим: Оптимізація по всьому бюджету.")
        
        all_data['Стандартний бюджет'] = all_data['TRP'] * all_data['Ціна']
        total_standard_budget = all_data['Стандартний бюджет'].sum()
        
        all_data['Доля по бюджету (%)'] = (all_data['Стандартний бюджет'] / total_standard_budget) * 100
        
        all_data['Відхилення'] = all_data.apply(lambda row: 0.20 if row['Доля по бюджету (%)'] >= 10 else 0.30, axis=1)
        all_data['Нижня межа'] = all_data['Стандартний бюджет'] * (1 - all_data['Відхилення'])
        all_data['Верхня межа'] = all_data['Стандартний бюджет'] * (1 + all_data['Відхилення'])

        c = -all_data[optimization_goal].values
        
        A_ub_total = [all_data['Ціна'].values]
        b_ub_total = [budget]
        
        A_lower = -pd.get_dummies(all_data['Канал']).mul(all_data['Ціна'], axis=0).values
        b_lower = -all_data['Нижня межа'].values
        A_upper = pd.get_dummies(all_data['Канал']).mul(all_data['Ціна'], axis=0).values
        b_upper = all_data['Верхня межа'].values
        
        A_total = [A_ub_total[0]] + list(A_lower) + list(A_upper)
        b_total = b_ub_total + list(b_lower) + list(b_upper)
        
        result = linprog(c, A_ub=A_total, b_ub=b_total, bounds=(0, None))
        
        if result.success:
            optimal_slots = result.x.round(0).astype(int)
            all_data['Оптимальні слоти'] = optimal_slots
            all_data['Оптимальний бюджет'] = optimal_slots * all_data['Ціна']
            all_results = all_data
        else:
            print(f"❌ Помилка оптимізації: {result.message}")

    if not all_results.empty:
        total_optimized_cost = all_results['Оптимальний бюджет'].sum()
        total_optimized_aff = (all_results['Оптимальні слоти'] * all_results['Aff']).sum()
        total_optimized_trp = (all_results['Оптимальні слоти'] * all_results['TRP']).sum()
        
        # Додано розрахунок TRP спліту
        all_results['TRP_оптимізований_спліт (%)'] = (all_results['Оптимальні слоти'] * all_results['TRP'] / total_optimized_trp) * 100

        print("\n📊 Загальні підсумкові показники по всій кампанії:")
        print(f"  - Використаний бюджет: {total_optimized_cost:.2f} грн")
        print(f"  - Максимальний загальний Aff: {total_optimized_aff:.2f}")
        print(f"  - Загальний TRP: {total_optimized_trp:.2f}")
        print("-" * 30)
        
        # Вивід результатів, включаючи TRP спліт
        print("\n📄 Результати оптимізації:")
        print(all_results[['Канал', 'СХ', 'Оптимальний бюджет', 'TRP_оптимізований_спліт (%)']])
        print("-" * 30)

        file_name = f'Оптимізація_результати_{optimization_mode}_{optimization_goal}.xlsx'
        save_results_to_excel(all_results[['Канал', 'СХ', 'Ціна', 'TRP', 'Aff', 'Стандартний бюджет', 'Оптимальний бюджет', 'Оптимальні слоти', 'TRP_оптимізований_спліт (%)']], file_name)
        
        plot_split_comparison(all_results, f"Оптимізація за {optimization_goal} ({'всього' if optimization_mode == 'total' else 'по СХ'})")
    
    return all_results

# --- Приклад використання ---
# Дані для різних СХ та БА (як окремі словники)
standard_data_by_sh = {
    'Sirius': {
        'Канал': ['ICTV', 'СТБ', 'НОВИЙ', 'ICTV2', 'ТЕТ', 'ОЦЕ', 'МЕГА'],
        'СХ': ['Sirius'] * 7,
        'Ціна_All 18-60': [18000, 10000, 11000, 12500, 9500, 7000, 8000],
        'TRP_All 18-60': [25.0, 15.0, 18.0, 16.0, 10.0, 8.0, 11.0],
        'Ціна_W 30+': [19500, 11000, 12500, 13500, 10500, 7500, 8800],
        'TRP_W 30+': [22.0, 14.0, 17.0, 15.0, 9.5, 7.5, 10.5]
    },
    'Space': {
        'Канал': ['ПЛЮСПЛЮС', 'БІГУДІ', 'Kvartal-TV', 'УНІАН'],
        'СХ': ['Space'] * 4,
        'Ціна_All 18-60': [6000, 5000, 4500, 3500],
        'TRP_All 18-60': [7.0, 6.0, 5.0, 4.0],
        'Ціна_W 30+': [6500, 5500, 5000, 4000],
        'TRP_W 30+': [6.5, 5.5, 4.5, 3.5]
    }
}

user_aff_by_sh = {
    'Sirius': {
        'Канал': ['ICTV', 'СТБ', 'НОВИЙ', 'ICTV2', 'ТЕТ', 'ОЦЕ', 'МЕГА'],
        'Aff': [95.0, 85.5, 90.1, 92.5, 88.0, 78.9, 80.0]
    },
    'Space': {
        'Канал': ['ПЛЮСПЛЮС', 'БІГУДІ', 'Kvartal-TV', 'УНІАН'],
        'Aff': [87.0, 81.5, 75.0, 70.0]
    }
}

# 2. Імітація вибору БА, цілі та режиму оптимізації
buying_audiences_choice = {
    'Sirius': 'All 18-60',
    'Space': 'W 30+'
}
total_budget = 500000
goal = 'Aff' # 'Aff' або 'TRP'
mode = 'total' # 'total' або 'per_sh'

# 3. Виклик функції оптимізації
optimize_split(standard_data_by_sh, user_aff_by_sh, total_budget, buying_audiences_choice, goal, mode)
