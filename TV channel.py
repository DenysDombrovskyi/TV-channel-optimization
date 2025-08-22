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

def optimize_split_by_sales_house_and_ba(standard_data_dict, user_aff_dict, budget, buying_audiences, optimization_goal):
    """
    Оптимізує канальний спліт окремо по кожному СХ, враховуючи допустимі відхилення,
    вибрану БА та ціль оптимізації.
    
    Параметри:
    - standard_data_dict (dict): Словник зі стандартними даними для кожного СХ.
    - user_aff_dict (dict): Словник з даними Aff від користувача для кожного СХ.
    - budget (int): Загальний рекламний бюджет.
    - buying_audiences (dict): Словник {СХ: БА}.
    - optimization_goal (str): 'Aff' або 'TRP'.
    """
    all_results = pd.DataFrame()
    
    # Розрахунок загального стандартного бюджету для визначення частки кожного СХ
    total_standard_budget = 0
    for sales_house in standard_data_dict:
        ba_key = buying_audiences.get(sales_house)
        if ba_key:
            df = pd.DataFrame(standard_data_dict[sales_house])
            df['Стандартний бюджет'] = df[f'TRP_{ba_key}'] * df[f'Ціна_{ba_key}']
            total_standard_budget += df['Стандартний бюджет'].sum()

    for sales_house in standard_data_dict:
        try:
            # 1. Завантаження даних та об'єднання
            ba_key = buying_audiences.get(sales_house)
            if not ba_key:
                print(f"Помилка: Не вказана баїнгова аудиторія для {sales_house}.")
                continue

            standard_df = pd.DataFrame(standard_data_dict[sales_house])
            user_df = pd.DataFrame(user_aff_dict[sales_house])
            
            # Об'єднання даних
            merged_df = pd.merge(standard_df, user_df, on='Канал')
            
            # Вибір колонок TRP і Ціна відповідно до вибраної БА
            merged_df['Ціна'] = merged_df[f'Ціна_{ba_key}']
            merged_df['TRP'] = merged_df[f'TRP_{ba_key}']
            
            print(f"✅ Починаємо оптимізацію для СХ: {sales_house} з БА: {ba_key}")
            print("-" * 30)

        except KeyError:
            print(f"Помилка: Немає даних для БА '{ba_key}' або СХ '{sales_house}'.")
            continue
        except Exception as e:
            print(f"Помилка при обробці даних: {e}")
            continue

        # 2. Розрахунок стандартних часток та меж відхилень
        merged_df['Стандартний бюджет'] = merged_df['TRP'] * merged_df['Ціна']
        
        group_standard_budget = merged_df['Стандартний бюджет'].sum()
        group_budget = (group_standard_budget / total_standard_budget) * budget

        merged_df['Доля по бюджету (%)'] = (merged_df['Стандартний бюджет'] / group_standard_budget) * 100
        
        merged_df['Відхилення'] = merged_df.apply(
            lambda row: 0.20 if row['Доля по бюджету (%)'] >= 10 else 0.30, axis=1
        )
        merged_df['Нижня межа'] = merged_df['Стандартний бюджет'] * (1 - merged_df['Відхилення'])
        merged_df['Верхня межа'] = merged_df['Стандартний бюджет'] * (1 + merged_df['Відхилення'])

        # 3. Налаштування параметрів для оптимізації
        goal_key = optimization_goal
        c = -merged_df[goal_key].values
        
        A_ub_group = [merged_df['Ціна'].values]
        b_ub_group = [group_budget]
        
        A_lower_bound_group = -pd.get_dummies(merged_df['Канал']).mul(merged_df['Ціна'], axis=0).values
        b_lower_bound_group = -merged_df['Нижня межа'].values

        A_upper_bound_group = pd.get_dummies(merged_df['Канал']).mul(merged_df['Ціна'], axis=0).values
        b_upper_bound_group = merged_df['Верхня межа'].values

        A_group = [A_ub_group[0]] + list(A_lower_bound_group) + list(A_upper_bound_group)
        b_group = b_ub_group + list(b_lower_bound_group) + list(b_upper_bound_group)
        
        bounds_group = [(0, None)] * len(merged_df)

        # 4. Виконання оптимізації
        result = linprog(c, A_ub=A_group, b_ub=b_group, bounds=bounds_group)

        # 5. Аналіз та збереження результатів
        if result.success:
            optimal_slots = result.x.round(0).astype(int)
            merged_df['Оптимальні слоти'] = optimal_slots
            merged_df['Оптимальний бюджет'] = optimal_slots * merged_df['Ціна']
            merged_df['Оптимальна доля (%)'] = (merged_df['Оптимальний бюджет'] / merged_df['Оптимальний бюджет'].sum()) * 100
            
            all_results = pd.concat([all_results, merged_df])
            
            print(f"\nОптимізація для {sales_house} завершена успішно!")
            print(merged_df[['Канал', 'Оптимальні слоти', 'Оптимальний бюджет', 'Оптимальна доля (%)']])
            print("-" * 30)
        else:
            print(f"❌ Помилка оптимізації для {sales_house}:", result.message)
            print("-" * 30)
    
    # 6. Підсумки та експорт
    if not all_results.empty:
        total_optimized_cost = all_results['Оптимальний бюджет'].sum()
        total_optimized_aff = (all_results['Оптимальні слоти'] * all_results['Aff']).sum()
        total_optimized_trp = (all_results['Оптимальні слоти'] * all_results['TRP']).sum()

        print("\n📊 Загальні підсумкові показники по всій кампанії:")
        print(f"  - Використаний бюджет: {total_optimized_cost:.2f} грн")
        print(f"  - Максимальний загальний Aff: {total_optimized_aff:.2f}")
        print(f"  - Загальний TRP: {total_optimized_trp:.2f}")
        print("-" * 30)
        
        save_results_to_excel(all_results[['Канал', 'СХ', 'Ціна', 'TRP', 'Aff', 'Стандартний бюджет', 'Оптимальний бюджет', 'Оптимальні слоти', 'Оптимальна доля (%)']], f'Оптимізація_результати_{optimization_goal}.xlsx')
        
        plot_split_comparison(all_results, f"Оптимізація за {optimization_goal}")
    
    return all_results

# --- Приклад використання ---
# 1. Імітація даних для різних СХ та БА (як окремі словники)
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

# 2. Імітація вибору БА та цілі оптимізації
buying_audiences_choice = {
    'Sirius': 'All 18-60',
    'Space': 'W 30+'
}
total_budget = 500000
goal = 'Aff' # Змініть на 'TRP', щоб оптимізувати за TRP

# 3. Виклик функції оптимізації
optimize_split_by_sales_house_and_ba(standard_data_by_sh, user_aff_by_sh, total_budget, buying_audiences_choice, goal)
