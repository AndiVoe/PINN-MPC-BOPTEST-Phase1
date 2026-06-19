import matplotlib.pyplot as plt
import numpy as np

def plot_results(results_data):
    models = ["RC Model", "PGNN (corr ON)", "PGNN (corr OFF)"]
    rmse_values = [results_data["RC Model"]["RMSE"], results_data["PGNN (corr ON)"]["RMSE"], results_data["PGNN (corr OFF)"]["RMSE"]]
    mae_values = [results_data["RC Model"]["MAE"], results_data["PGNN (corr ON)"]["MAE"], results_data["PGNN (corr OFF)"]["MAE"]]
    r2_values = [results_data["RC Model"]["R2"], results_data["PGNN (corr ON)"]["R2"], results_data["PGNN (corr OFF)"]["R2"]]

    x = np.arange(len(models))  # the label locations
    width = 0.25  # the width of the bars

    fig, ax = plt.subplots(figsize=(10, 6))
    rects1 = ax.bar(x - width, rmse_values, width, label='RMSE')
    rects2 = ax.bar(x, mae_values, width, label='MAE')
    rects3 = ax.bar(x + width, r2_values, width, label='R2')

    ax.set_ylabel('Value')
    ax.set_title('Model Performance Metrics')
    ax.set_xticks(x)
    ax.set_xticklabels(models)
    ax.legend()

    def autolabel(rects):
        """Attach a text label above each bar in *rects*, displaying its height."""
        for rect in rects:
            height = rect.get_height()
            ax.annotate(f'{height:.4f}',
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3),  # 3 points vertical offset
                        textcoords="offset points",
                        ha='center', va='bottom')

    autolabel(rects1)
    autolabel(rects2)
    autolabel(rects3)

    fig.tight_layout()
    plt.savefig("model_performance_plot.png")
    print("Plot saved to model_performance_plot.png")

if __name__ == "__main__":
    # The results from the terminal output
    results = {
        "RC Model": {"RMSE": 0.9421, "MAE": 0.7836, "R2": 0.5953},
        "PGNN (corr ON)": {"RMSE": 0.4802, "MAE": 0.3827, "R2": 0.8948},
        "PGNN (corr OFF)": {"RMSE": 0.9421, "MAE": 0.7836, "R2": 0.5953}
    }
    plot_results(results)
