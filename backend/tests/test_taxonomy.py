from app.services.taxonomy import get_taxonomy, requirements_from_jd


def test_taxonomy_avoids_substring_false_positives():
    taxonomy = get_taxonomy()

    assert taxonomy.names("We use JavaScript and TypeScript.") == ["JavaScript", "TypeScript"]
    assert "Java" not in taxonomy.names("We use JavaScript.")
    assert "React" not in taxonomy.names("The reactive system is fast.")
    assert "Git" not in taxonomy.names("We are digital-first.")
    assert taxonomy.names("We build with C++ and C#.")[:2] == ["C#", "C++"]


def test_taxonomy_keeps_pytorch_and_tensorflow_distinct():
    taxonomy = get_taxonomy()
    names = taxonomy.names("PyTorch and TensorFlow are both used.")
    assert "PyTorch" in names
    assert "TensorFlow" in names
    assert taxonomy.names("TensorFlow only") == ["TensorFlow"]


def test_taxonomy_longer_alias_wins():
    taxonomy = get_taxonomy()
    names = taxonomy.names("We use React Native and Node.js.")
    assert "React Native" in names
    assert "React" not in names
    assert "Node.js" in names


def test_jd_absorbs_observability_tools():
    taxonomy = get_taxonomy()
    requirements = requirements_from_jd(
        "Nice to have: observability with Prometheus or Grafana.",
        taxonomy,
    )
    names = {item.text for item in requirements}
    assert "Observability" in names
    assert "Prometheus" not in names
    assert "Grafana" not in names


def test_jd_keeps_a_heavier_tool_requirement():
    taxonomy = get_taxonomy()
    requirements = requirements_from_jd(
        "Preferred: observability.\nMust have Grafana.",
        taxonomy,
    )
    names = {item.text for item in requirements}
    assert "Grafana" in names


def test_jd_requirements_are_weighted_by_context():
    taxonomy = get_taxonomy()
    requirements = requirements_from_jd(
        "Must have Python and FastAPI.\nNice to have Kubernetes.\nPostgreSQL required.",
        taxonomy,
    )
    by_name = {item.text: item for item in requirements}
    assert by_name["Python"].must_have is True
    assert by_name["FastAPI"].must_have is True
    assert by_name["Kubernetes"].weight == 1
    assert by_name["PostgreSQL"].must_have is True
