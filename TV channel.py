import pandas as pd
from scipy.optimize import linprog

def save_results_to_excel(results_df, file_name):
    """
    Зберігає результати оптимізації у файл Excel.
    """
    try:
        results_df.to_excel(file_name, index=False)
        print(f"\n✅ Результати оптимізації успішно збережено у файл: '{file_name}'")
    except Exception as e:
        print(f"\n❌ Помилка при збереженні файлу: {e}")

def optimize_split_by_sales_house_and_ba(standard_data_dict, user_aff_dict, budget, buying_audiences):
    """
    Оптимізує канальний спліт окремо по кожному СХ, враховуючи допустимі відхилення
    та вибрану баїнгову аудиторію.

    Параметри:
    - standard_data_dict (dict): Словник зі стандартними даними для кожного СХ.
    - user_aff_dict (dict): Словник з даними Aff від користувача для кожного СХ.
    - budget (int): Загальний рекламний бюджет.
    - buying_audiences (dict): Словник, де ключ - це СХ, а значення - вибрана БА.

    Повертає:
    - DataFrame з оптимальним розподілом або None у разі помилки.
    """
    all_results = pd.DataFrame()
    
    # Розрахунок загального стандартного бюджету для визначення частки кожного СХ
    total_standard_budget = 0
    for sales_house in standard_data_dict:
        ba_key = buying_audiences[sales_house]
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
            print(merged_df[['Канал', 'СХ', 'Ціна', 'TRP']])
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
        c = -merged_df['Aff'].values
        
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
    
    # 6. Підсумки по всій кампанії та експорт
    if not all_results.empty:
        total_optimized_cost = all_results['Оптимальний бюджет'].sum()
        total_optimized_aff = (all_results['Оптимальні слоти'] * all_results['Aff']).sum()
        total_optimized_trp = (all_results['Оптимальні слоти'] * all_results['TRP']).sum()

        print("\n📊 Загальні підсумкові показники по всій кампанії:")
        print(f"  - Використаний бюджет: {total_optimized_cost:.2f} грн")
        print(f"  - Максимальний загальний Aff: {total_optimized_aff:.2f}")
        print(f"  - Загальний TRP: {total_optimized_trp:.2f}")
        print("-" * 30)
        
        # Експорт результатів у файл
        save_results_to_excel(all_results, 'Оптимізація_спліта_результати.xlsx')
    
    return all_results

# --- Приклад використання з імітацією вибору БА ---
standard_data_by_sh = {
    'Sirius': {
        'Канал': ['ICTV', 'СТБ', 'НОВИЙ', 'ТЕТ', 'ОЦЕ', 'МЕГА', 'ICTV2'],
        'СХ': ['Sirius'] * 7,
        'Ціна_All 18-60': [18000, 10000, 11000, 9500, 7000, 8000, 12500],
        'TRP_All 18-60': [25.0, 15.0, 18.0, 10.0, 8.0, 11.0, 16.0],
        'Ціна_W 30+': [19500, 11000, 12500, 10500, 7500, 8800, 13500],
        'TRP_W 30+': [22.0, 14.0, 17.0, 9.5, 7.5, 10.5, 15.0]
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
        'Канал': ['ICTV', 'СТБ', 'НОВИЙ', 'ТЕТ', 'ОЦЕ', 'МЕГА', 'ICTV2'],
        'Aff': [95.0, 85.5, 90.1, 88.0, 78.9, 80.0, 92.5]
    },
    'Space': {
        'Канал': ['ПЛЮСПЛЮС', 'БІГУДІ', 'Kvartal-TV', 'УНІАН'],
        'Aff': [87.0, 81.5, 75.0, 70.0]
    }
}

# 2. Імітація вибору БА користувачем (у реальному додатку це був би випадаючий список)
buying_audiences_choice = {
    'Sirius': 'All 18-60',
    'Space': 'W 30+'
}

# 3. Виклик функції оптимізації
total_budget = 500000
optimize_split_by_sales_house_and_ba(standard_data_by_sh, user_aff_by_sh, total_budget, buying_audiences_choice)
