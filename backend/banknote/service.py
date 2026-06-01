from backend.common.exceptions import ResourceNotFoundError
from backend.banknote import dao
from backend.common.excel import create_excel_file_streaming, generate_filename
import csv
from io import StringIO
from datetime import datetime

class BanknoteService:

    @staticmethod
    def _format_csv_value(value):
        if value is None:
            return ""
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return value

    def get_paged_banknote_counts(self, page, per_page, filter_params=None, sort_by='count_time', sort_order='desc'):
        """
        获取分页的过钞记录，支持筛选和排序。
        """
        return dao.get_all_banknote_counts(page, per_page, filter_params, sort_by, sort_order, export=False)

    def get_currencies_by_count_id(self, count_id):
        """
        获取指定过钞记录的所有币种统计。
        """
        count_record = dao.get_banknote_count_by_id(count_id)
        if not count_record:
            raise ResourceNotFoundError(f"Banknote count record with ID '{count_id}' does not exist.")
        return count_record.currencies

    def get_detailed_data_by_count_id(self, count_id):
        """
        获取指定过钞记录的所有详细数据。
        """
        if not dao.get_banknote_count_by_id(count_id):
            raise ResourceNotFoundError(f"Banknote count record with ID '{count_id}' does not exist.")
        return dao.get_detailed_data_by_count_id(count_id)

    def delete_banknote_count(self, count_id):
        """
        逻辑删除一条过钞记录。
        """
        record = dao.get_banknote_count_by_id(count_id)
        if not record:
            raise ResourceNotFoundError(f"Banknote count record with ID '{count_id}' does not exist.")
        dao.delete_banknote_count(record)

    def export_banknote_detailed_data(self, filter_params=None, sort_by='count_time', sort_order='desc'):
        """
        导出筛选/排序后的 BanknoteCount 关联的 BanknoteDetailedData 明细。
        输出列顺序：device_identifier、stacker、institution_name、institution_code、serial_number、note_value、currency_code、note_version、error_type、error_code、error_group、count_time。
        """
        headers = [
            {"key": "device_identifier", "title": "Device ID", "width": 25},
            {"key": "stacker", "title": "Stacker", "width": 10},
            {"key": "institution_name", "title": "Institution Name", "width": 18},
            {"key": "institution_code", "title": "Institution Code", "width": 16},
            {"key": "serial_number", "title": "Serial Number", "width": 28},
            {"key": "note_value", "title": "Note Value", "width": 12},
            {"key": "currency_code", "title": "Currency Code", "width": 12},
            {"key": "note_version", "title": "Note Version", "width": 12},
            {"key": "error_type", "title": "Error Type", "width": 12},
            {"key": "error_code", "title": "Error Code", "width": 30},
            {"key": "error_group", "title": "Error Group", "width": 12},
            {"key": "count_time", "title": "Count Time", "width": 25},
        ]

        detailed_rows_iter = dao.stream_banknote_detailed_rows(
            filter_params=filter_params,
            sort_by=sort_by,
            sort_order=sort_order
        )
        excel_buffer = create_excel_file_streaming(headers, detailed_rows_iter, sheet_name="banknote_detailed")
        filename = generate_filename("banknote_detailed")
        return excel_buffer, filename

    def export_banknote_detailed_data_csv(self, filter_params=None, sort_by='count_time', sort_order='desc', flush_rows=5000):
        """
        以流式 CSV 方式导出筛选/排序后的明细数据。
        """
        header_titles = [
            "Device ID",
            "Stacker",
            "Institution Name",
            "Institution Code",
            "Serial Number",
            "Note Value",
            "Currency Code",
            "Note Version",
            "Error Type",
            "Error Code",
            "Error Group",
            "Count Time",
        ]

        detailed_rows_iter = dao.stream_banknote_detailed_rows(
            filter_params=filter_params,
            sort_by=sort_by,
            sort_order=sort_order
        )

        def line_generator():
            output = StringIO()
            writer = csv.writer(output)

            writer.writerow(header_titles)
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

            row_count = 0
            for row in detailed_rows_iter:
                writer.writerow([self._format_csv_value(v) for v in row])
                row_count += 1
                if row_count % flush_rows == 0:
                    yield output.getvalue()
                    output.seek(0)
                    output.truncate(0)

            remaining = output.getvalue()
            if remaining:
                yield remaining

        filename = generate_filename("banknote_detailed").replace('.xlsx', '.csv')
        return line_generator(), filename

    def get_chart_data(self, args: dict):
        """
        在筛选条件基础上进行聚合：
        - group_by: institution|device|count_time
        - metric: total_passed_count|failed_count|total_amount|currency_count -> 返回 value
        - time_agg: day|week|month（仅 group_by=count_time 时需要）
        - sort_order: asc|desc（count_time 建议按时间正序）
        - limit: Top N
        """
        group_by = args['group_by']
        metric = args['metric']
        sort_order = args.get('sort_order', 'desc')
        limit = args.get('limit')
        time_agg = args.get('time_agg')

        # 将聚合查询下沉到 DAO
        filter_params = {
            'device_identifier': args.get('device_identifier'),
            'institution_name': args.get('institution_name'),
            'count_time_start': args.get('count_time_start'),
            'count_time_end': args.get('count_time_end'),
        }
        records = dao.aggregate_banknote_counts(
            group_by=group_by,
            metric=metric,
            filter_params=filter_params,
            time_agg=time_agg,
            sort_order=sort_order,
            limit=limit
        )
        return {"records": records}

#-------------------------------此部分为新api的主从库分离示例----------------------------------
    def get_summary_stats(self):
        """
        获取 overview 统计概览（走从库）。
        """
        return dao.get_summary_stats()
#---------------------------------------------------------------------------------------------
banknote_service = BanknoteService()