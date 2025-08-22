import pandas as pd
from scipy.optimize import linprog
import matplotlib.pyplot as plt
import sys
import os
import tkinter as tk
from tkinter import filedialog

def display_logo():
    """
    Виводить текстовий логотип Dentsu X на початку програми.
    """
    logo = r"""
██████╗  █████╗ ███╗   ██╗████████╗██╗   ██╗ ██╗
██╔════╝ ██╔══██╗████╗  ██║╚══██╔══╝╚██╗ ██╔╝██╔╝
██║  ██╗ ███████║██╔██╗ ██║   ██║    ╚████╔╝ ██║
██║  ╚██╗██╔══██║██║╚██╗██║   ██║     ╚██╔╝  ██║
╚██████╔╝██║  ██║██║ ╚████║   ██║      ██║   ██║
 ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝      ╚═╝   ╚═╝
  TV Channel Optimization Tool by Dentsu X
    """
    print(logo)
    print("-" * 50)
    print("Ласкаво просимо до програми оптимізації рекламних кампаній!")
    print("-" * 50)

def load_data_from_excel(file_path):
    """
    Завантажує дані з вказаного файлу Excel.
    """
    if not os.path.exists(file_path):
        print(f"❌ Помилка: Файл '{file_path}' не знайдено.")
        return None, None
        
    try:
        standard_data_sheet = "Сп-во"
        aff_data_sheet = "Оптимізація спліта (викл)"

        standard_df = pd.read_excel(file_path, sheet_name=standard_data_sheet, skiprows=1)
        aff_df = pd.read_excel(file_path, sheet_name=aff_data_sheet, skiprows=7)
        
        aff_df = aff_df.iloc[:, [1, 5]].copy()
        aff_df.columns = ['Канал', 'Aff']

        print(f"\n✅ Дані успішно завантажено з файлу '{os.path.basename(file_path)}' з листів '{standard_data_sheet}' та '{aff_data_sheet}'.")
        return standard_df, aff_df
    except Exception as e:
        print(f"❌ Помилка при читанні файлу Excel: {e}")
        return None, None

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
    results_df['Доля стандартного бюджету'] = (results_df['Стандартний бюджет'] / results_df['Стандартний бюджет'].sum()) * 100
    results_df['Доля оптимізованого бюджету'] = (results_df['Оптимальний бюджет'] / results_df['Оптимальний бюджет'].sum()) * 100
    
    fig, axes = plt.subplots(1, 2, figsize=(18, 8))
    fig.suptitle(f'Оптимізація канального спліта: {title}', fontsize=16)

    axes[0].set_title('Порівняння частки бюджету (%)')
    labels = results_df['Канал']
    standard_share = results_df['Доля стандартного бюджету']
    optimal_share = results_df['Доля оптимізованого бюджету']
    
    x = range(len(labels))
    width = 0.35
    
    axes[0].bar(x, standard_share, width, label='Стандартний спліт', color='gray')
    axes[0].bar([p + width for p in x], optimal_share, width, label='Оптимізований спліт', color='skyblue')

    axes[0].set_ylabel('Частка бюджету, %')
    axes[0].set_xticks([p + width / 2 for p in x])
    axes[0].set_xticklabels(labels, rotation=45, ha="right")
    axes[0].legend()
    axes[0].grid(axis='y', linestyle='--', alpha=0.7)
    
    axes[1].set_title('Кількість слотів (Оптимізований спліт)')
    optimal_slots = results_df['Оптимальні слоти']
    
    axes[1].bar(labels, optimal_slots, color='skyblue')
    axes[1].set_ylabel('Кількість слотів')
    axes[1].set_xticklabels(labels, rotation=45, ha="right")
    axes[1].grid(axis='y', linestyle='--', alpha=0.7)

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.show()

def optimize_split(all_data, budget, buying_audiences, optimization_goal, optimization_mode):
    """
    Основна функція для оптимізації канального спліта.
    """
    all_data = all_data.copy()
    all_data['Ціна'] = all_data.apply(lambda row: row[f'Ціна_{buying_audiences[row["СХ"]]}'], axis=1)
    all_data['TRP'] = all_data.apply(lambda row: row[f'TRP_{buying_audiences[row["СХ"]]}'], axis=1)
    
    all_results = pd.DataFrame()
    
    if optimization_mode == 'per_sh':
        print("\nВибрано режим: Оптимізація по кожному СХ окремо.")
        
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
        
        all_results['TRP_оптимізований_спліт (%)'] = (all_results['Оптимальні слоти'] * all_results['TRP'] / total_optimized_trp) * 100

        print("\n📊 Загальні підсумкові показники по всій кампанії:")
        print(f"  - Використаний бюджет: {total_optimized_cost:.2f} грн")
        print(f"  - Максимальний загальний Aff: {total_optimized_aff:.2f}")
        print(f"  - Загальний TRP: {total_optimized_trp:.2f}")
        print("-" * 30)
        
        print("\n📄 Результати оптимізації:")
        print(all_results[['Канал', 'СХ', 'Оптимальний бюджет', 'TRP_оптимізований_спліт (%)']])
        print("-" * 30)

        file_name = f'Оптимізація_результати_{optimization_mode}_{optimization_goal}.xlsx'
        save_results_to_excel(all_results[['Канал', 'СХ', 'Ціна', 'TRP', 'Aff', 'Стандартний бюджет', 'Оптимальний бюджет', 'Оптимальні слоти', 'TRP_оптимізований_спліт (%)']], file_name)
        
        plot_split_comparison(all_results, f"Оптимізація за {optimization_goal} ({'всього' if optimization_mode == 'total' else 'по СХ'})")
    
    return all_results

# --- Інтерактивне використання ---
if __name__ == "__main__":
    display_logo()

    # 1. Запит на вибір файлу через вікно
    print("Будь ласка, оберіть ваш Excel-файл у вікні, що з'явиться.")
    
    root = tk.Tk()
    root.withdraw() # Заховати головне вікно Tkinter
    excel_file = filedialog.askopenfilename(
        title="Оберіть файл Excel",
        filetypes=[("Excel files", "*.xlsx *.xlsm")]
    )
    
    if not excel_file:
        print("❌ Файл не обрано. Програму завершено.")
        sys.exit()

    standard_df, aff_df = load_data_from_excel(excel_file)
    
    if standard_df is None or aff_df is None:
        sys.exit()

    # Об'єднання завантажених даних
    all_data_merged = pd.merge(standard_df, aff_df, on='Канал')
    
    all_sh = all_data_merged['СХ'].unique()
    all_ba = [col.replace('Ціна_', '') for col in all_data_merged.columns if 'Ціна_' in col]
    
    # 2. Запит параметрів у користувача
    print("🎬 Налаштування параметрів оптимізації:")

    buying_audiences_choice = {}
    for sh in all_sh:
        print(f"\nДля СХ '{sh}' доступні БА: {', '.join(all_ba)}")
        ba_choice = input(f"Оберіть БА для СХ '{sh}': ")
        if ba_choice not in all_ba:
            print(f"❌ Некоректна БА. Використано першу доступну: '{all_ba[0]}'")
            ba_choice = all_ba[0]
        buying_audiences_choice[sh] = ba_choice
    
    while True:
        try:
            total_budget = int(input("\nВведіть загальний рекламний бюджет (наприклад, 500000): "))
            if total_budget <= 0:
                print("❌ Бюджет повинен бути додатним числом. Спробуйте ще раз.")
                continue
            break
        except ValueError:
            print("❌ Введіть, будь ласка, числове значення.")

    while True:
        goal = input("Оберіть мету оптимізації ('Aff' або 'TRP'): ").strip().lower()
        if goal in ['aff', 'trp']:
            break
        else:
            print("❌ Некоректна мета. Введіть 'Aff' або 'TRP'.")
    
    while True:
        mode = input("Оберіть режим оптимізації ('total' - для всієї кампанії, 'per_sh' - по кожному СХ): ").strip().lower()
        if mode in ['total', 'per_sh']:
            break
        else:
            print("❌ Некоректний режим. Введіть 'total' або 'per_sh'.")

    # 3. Виклик функції оптимізації з введеними параметрами
    print("\n🚀 Запуск оптимізації...")
    optimize_split(all_data_merged, total_budget, buying_audiences_choice, goal.upper(), mode)
